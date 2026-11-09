"""Engine + gateway behaviour: sync between stations, control lock, validation, layouts."""
from __future__ import annotations

import time

import pytest
from starlette.testclient import TestClient

from nexusui import Engine, WriteRejected, discover_widgets
from nexusui.widgets.motor.backend import Motor


def recv_until(ws, pred, limit=200):
    for _ in range(limit):
        m = ws.receive_json()
        if pred(m):
            return m
    raise AssertionError("expected message never arrived")


def is_delta(ch, value=None):
    return lambda m: m["t"] == "d" and ch in m["v"] and (value is None or m["v"][ch] == value)


@pytest.fixture
def eng(tmp_path):
    e = Engine("Test", control="lock", app_dir=tmp_path, watchdog=0.4)
    e.channel("lamp", "bool", writable=True)
    e.channel("level", writable=True, min=0, max=10)
    e.channel("ro", initial=1.0)
    e.channel("temp", warn_high=50, alarm_high=80)
    e.channel("mode", "enum", options=["SAFE", "ARMED"], writable=True)
    e.lost = []

    @e["level"].on_write
    def _lvl(v):
        if v == 7:
            raise WriteRejected("seven is unlucky")
        return round(v, 1)

    @e.command("go")
    def _go():
        e["lamp"].set(True)

    @e.on_control_lost
    def _lost():
        e.lost.append(time.time())

    return e


@pytest.fixture
def client(eng):
    with TestClient(eng.app) as c:
        yield c


def test_hello_has_catalog_and_snapshot(client):
    with client.websocket_connect("/ws?name=Alpha") as ws:
        h = ws.receive_json()
        assert h["t"] == "hello"
        assert h["you"]["name"] == "Alpha"
        assert {c["name"] for c in h["channels"]} >= {"lamp", "level", "ro", "mode"}
        assert h["values"]["ro"] == 1.0
        assert h["control"]["holder"] is None


def test_write_reaches_other_station_before_ack(client):
    with client.websocket_connect("/ws?name=A") as a, client.websocket_connect("/ws?name=B") as b:
        a.receive_json(); b.receive_json()
        a.send_json({"t": "claim", "id": 1})
        recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 1)
        a.send_json({"t": "write", "id": 2, "ch": "lamp", "v": True})
        # writer sees the new state first, then the ack
        first = recv_until(a, lambda m: m["t"] in ("d", "ack") and (m["t"] == "ack" or "lamp" in m["v"]))
        assert first["t"] == "d" and first["v"]["lamp"] is True
        assert first["w"]["lamp"]["by"] == "A"
        recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2 and m["ok"])
        # the other station gets the change with who made it
        d = recv_until(b, is_delta("lamp", True))
        assert d["w"]["lamp"]["by"] == "A"


def test_view_only_station_cannot_write(client):
    with client.websocket_connect("/ws?name=A") as a:
        a.receive_json()
        a.send_json({"t": "write", "id": 1, "ch": "lamp", "v": True})
        ack = recv_until(a, lambda m: m["t"] == "ack")
        assert not ack["ok"] and "View only" in ack["error"]


@pytest.mark.parametrize("ch,v,err", [
    ("level", 11, "maximum"), ("level", "x", "number"), ("ro", 2, "read-only"),
    ("mode", "FIRE", "one of"), ("lamp", 1, "true or false"), ("level", 7, "unlucky"), ("nope", 1, "Unknown"),
])
def test_writes_are_validated(client, ch, v, err):
    with client.websocket_connect("/ws") as a:
        a.receive_json()
        a.send_json({"t": "claim", "id": 1})
        a.send_json({"t": "write", "id": 2, "ch": ch, "v": v})
        ack = recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2)
        assert not ack["ok"] and err in ack["error"]


def test_handler_can_adjust_value(client, eng):
    with client.websocket_connect("/ws") as a:
        a.receive_json()
        a.send_json({"t": "claim", "id": 1})
        a.send_json({"t": "write", "id": 2, "ch": "level", "v": 3.14159})
        recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2 and m["ok"])
        assert eng["level"].value == 3.1


def test_takeover_needs_force_and_disconnect_drops_control(client, eng):
    with client.websocket_connect("/ws?name=A") as a:
        a.receive_json()
        a.send_json({"t": "claim", "id": 1})
        recv_until(a, lambda m: m["t"] == "ack")
        with client.websocket_connect("/ws?name=B") as b:
            b.receive_json()
            b.send_json({"t": "claim", "id": 1})
            assert "has control" in recv_until(b, lambda m: m["t"] == "ack")["error"]
            b.send_json({"t": "claim", "id": 2, "force": True})
            assert recv_until(b, lambda m: m["t"] == "ack" and m["id"] == 2)["ok"]
            ctl = recv_until(a, lambda m: m["t"] == "control" and m["holder_name"] == "B")
            assert ctl["holder"] is not None
        # B (the operator) disconnected: control released, safe handler ran
        recv_until(a, lambda m: m["t"] == "control" and m["holder"] is None)
    deadline = time.time() + 2
    while not eng.lost and time.time() < deadline:
        time.sleep(0.02)
    assert eng.lost


def test_watchdog_drops_silent_operator(client, eng):
    with client.websocket_connect("/ws?name=A") as a:
        a.receive_json()
        a.send_json({"t": "claim", "id": 1})
        recv_until(a, lambda m: m["t"] == "ack")
        # no pings for longer than the 0.4 s watchdog
        m = recv_until(a, lambda m: m["t"] == "control" and m["holder"] is None, limit=500)
        assert m["holder"] is None
        alerts = recv_until(a, lambda m: m["t"] == "alerts")
        assert any(x["key"] == "control_lost" for x in alerts["list"])


def test_limit_alerts_raise_and_clear(client, eng):
    with client.websocket_connect("/ws") as a:
        a.receive_json()
        eng["temp"].set(90)
        m = recv_until(a, lambda m: m["t"] == "alerts" and m["list"])
        assert m["list"][0]["level"] == "alarm" and m["list"][0]["active"]
        eng["temp"].set(20)
        m = recv_until(a, lambda m: m["t"] == "alerts" and not m["list"][0]["active"])
        assert m["list"][0]["key"] == "limit:temp"


def test_command_runs_and_broadcasts(client, eng):
    with client.websocket_connect("/ws?name=A") as a, client.websocket_connect("/ws?name=B") as b:
        a.receive_json(); b.receive_json()
        a.send_json({"t": "claim", "id": 1})
        a.send_json({"t": "cmd", "id": 2, "name": "go"})
        assert recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2)["ok"]
        recv_until(b, is_delta("lamp", True))


def test_layouts_save_load_and_validate(client, eng):
    assert client.get("/api/layouts/default").json()["tabs"]  # auto layout before any save
    layout = {"title": "T", "tabs": [{"id": "a", "title": "A", "widgets": []}]}
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        r = client.put("/api/layouts/ops", json=layout, headers={"x-station-name": "Bravo"})
        assert r.status_code == 200
        ev = recv_until(ws, lambda m: m["t"] == "layout")
        assert ev["name"] == "ops" and ev["by"] == "Bravo"
    assert client.get("/api/layouts/ops").json()["title"] == "T"
    assert (eng.app_dir / "layouts" / "ops.json").exists()
    assert client.put("/api/layouts/..%2Fevil", json=layout).status_code in (400, 404, 405)
    assert client.put("/api/layouts/bad name!", json=layout).status_code == 400
    assert client.put("/api/layouts/bad", json={"no": "tabs"}).status_code == 400
    names = [x["name"] for x in client.get("/api/layouts").json()["layouts"]]
    assert "ops" in names


def test_app_widgets_extend_and_override_framework(tmp_path):
    w = tmp_path / "widgets" / "gauge"
    w.mkdir(parents=True)
    (w / "backend.py").write_text(
        "from nexusui.widget import WidgetSpec\n"
        "SPEC = WidgetSpec(type='gauge', label='Custom Gauge', sizes=['s'])\n")
    specs = discover_widgets(tmp_path)
    assert specs["gauge"].label == "Custom Gauge"
    assert "motor" in specs and "diagram" in specs


def test_device_interlock_refuses_start_while_inhibited(tmp_path):
    e = Engine("T", app_dir=tmp_path)
    t = Motor(e, "t1", "Drive")
    t.inhibit = "bumper pressed"
    assert "bumper" in t.on._interlock(True)
    t.inhibit = None
    assert t.on._interlock(True) is None
    assert t.on._interlock(False) is None          # stopping is never interlocked
    assert e.devices["t1"].describe()["channels"]["rpm"] == "t1.rpm"


def test_channel_interlock_blocks_write_and_publishes_reason(tmp_path):
    e = Engine("T", app_dir=tmp_path)
    pump = e.channel("pump", "bool", writable=True, initial=True)
    valve = e.channel("valve", "bool", writable=True)
    valve.interlock(lambda opening: "pump is running" if opening and pump.value else None)
    with TestClient(e.app) as c, c.websocket_connect("/ws?name=A") as a:
        h = a.receive_json()
        a.send_json({"t": "claim", "id": 1})
        a.send_json({"t": "write", "id": 2, "ch": "valve", "v": True})
        ack = recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2)
        assert not ack["ok"] and "pump is running" in ack["error"]
        # the live reason reaches stations so every control can show it
        m = recv_until(a, lambda m: m["t"] == "locks" and "valve" in m["v"], limit=500) if "valve" not in h["locks"] else h
        assert "pump is running" in (m.get("v") or m.get("locks"))["valve"]
        a.send_json({"t": "write", "id": 3, "ch": "pump", "v": False})
        # the cleared lock is pushed with the new state, before the ack
        seen = {}
        while not ("ack" in seen and "locks" in seen):
            m = a.receive_json()
            if m["t"] == "ack" and m["id"] == 3:
                seen["ack"] = m
            elif m["t"] == "locks" and "valve" in m["v"]:
                seen["locks"] = m
        assert seen["ack"]["ok"] and seen["locks"]["v"]["valve"] is None
        a.send_json({"t": "write", "id": 4, "ch": "valve", "v": True})
        assert recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 4)["ok"]


def test_override_bypasses_interlocks_only_for_operator_and_ends_with_control(tmp_path):
    e = Engine("T", app_dir=tmp_path)
    valve = e.channel("valve", "bool", writable=True)
    valve.interlock(lambda opening: "always locked" if opening else None)
    with TestClient(e.app) as c, c.websocket_connect("/ws?name=A") as a, c.websocket_connect("/ws?name=B") as b:
        a.receive_json(); b.receive_json()
        # a viewer cannot override
        b.send_json({"t": "override", "id": 1, "on": True})
        assert "operating station" in recv_until(b, lambda m: m["t"] == "ack")["error"]
        a.send_json({"t": "claim", "id": 1})
        recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 1)
        a.send_json({"t": "write", "id": 2, "ch": "valve", "v": True})
        assert not recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 2)["ok"]
        a.send_json({"t": "override", "id": 3, "on": True})
        ctl = recv_until(b, lambda m: m["t"] == "control" and m.get("override"))
        assert ctl["override_by"] == "A"
        a.send_json({"t": "write", "id": 4, "ch": "valve", "v": True})
        assert recv_until(a, lambda m: m["t"] == "ack" and m["id"] == 4)["ok"]
        assert valve.value is True
        assert any("OVERRODE" in x["msg"] for x in e._logs)
        assert e._alerts["override"]["active"]
        # releasing control ends the override
        a.send_json({"t": "release", "id": 5})
        recv_until(b, lambda m: m["t"] == "control" and m["holder"] is None and not m["override"])
        assert not e.override and not e._alerts["override"]["active"]


def test_desktop_does_not_open_a_window_when_the_port_is_taken(tmp_path, monkeypatch):
    import socket

    from nexusui import desktop
    monkeypatch.setattr(desktop, "open_window", lambda *a, **k: pytest.fail("opened a window with no server behind it"))
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        e = Engine("Test", app_dir=tmp_path)
        with pytest.raises(SystemExit, match="could not start"):
            e.run(host="127.0.0.1", port=busy.getsockname()[1], desktop=True, log_level="critical")


def test_run_defaults_to_a_private_window_and_serves_browsers_on_request(monkeypatch):
    from nexusui.engine import _run_target
    monkeypatch.setenv("DISPLAY", ":0")     # a Linux test machine counts as having a screen
    assert _run_target(None, None, None) == (True, "127.0.0.1", 0)          # private, system-chosen port
    assert _run_target(None, None, False) == (False, "0.0.0.0", 8000)       # --browser
    assert _run_target("0.0.0.0", 8000, None) == (True, "0.0.0.0", 8000)    # window here, browsers elsewhere
    monkeypatch.delenv("DISPLAY")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    assert _run_target(None, None, None) == (False, "0.0.0.0", 8000)        # no screen: serve browsers
