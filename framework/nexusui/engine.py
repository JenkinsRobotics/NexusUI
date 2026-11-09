"""
nexusui.engine
---------------
The station engine: owns hardware state and serves it to any number of UIs.

Design rules
  * Hardware code runs in its own threads (``@engine.loop``) and never waits
    on a UI. The UI can freeze, disconnect or crash without touching control.
  * Every value lives in a Channel. UIs read channels and request writes;
    the engine validates each write (type, range, control lock, your handler)
    before anything reaches hardware.
  * Discrete changes (valves, modes, writes from any station) are pushed to
    every station immediately. Fast analog telemetry is coalesced to the
    display frame rate so slow links never build a backlog.
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import itertools
import json
import logging
import math
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable

log = logging.getLogger("nexusui")

KINDS = ("number", "bool", "enum", "text")
TONES = ("ok", "warn", "alarm", "info", "off", "active")


class WriteRejected(Exception):
    """Raise from a write or command handler to refuse it with a message."""


# --------------------------------------------------------------------------
# Channels
# --------------------------------------------------------------------------
IO_KINDS = {"DO": ("bool", True), "DI": ("bool", False), "AO": ("number", True), "AI": ("number", False)}


class Channel:
    """One named value. Hardware threads call ``set``; UIs request writes."""

    def __init__(
        self,
        engine: "Engine",
        name: str,
        kind: str = "number",
        *,
        label: str | None = None,
        unit: str = "",
        group: str = "",
        min: float | None = None,
        max: float | None = None,
        step: float | None = None,
        precision: int | None = None,
        fmt: str = "fixed",
        log_scale: bool = False,
        options: Iterable[str] | None = None,
        states: dict[str, str] | None = None,
        writable: bool = False,
        warn_high: float | None = None,
        alarm_high: float | None = None,
        warn_low: float | None = None,
        alarm_low: float | None = None,
        initial: Any = None,
        description: str = "",
        urgent: bool | None = None,
        quiet: bool = False,
    ):
        if kind not in KINDS:
            raise ValueError(f"channel kind must be one of {KINDS}")
        self._engine = engine
        self.name = name
        self.kind = kind
        self.label = label or name.split(".")[-1].replace("_", " ").title()
        self.unit = unit
        self.group = group or (name.split(".")[0] if "." in name else "")
        self.min, self.max, self.step = min, max, step
        self.precision = precision
        self.fmt = fmt  # "fixed" | "sci" | "int"
        self.log_scale = log_scale
        self.options = list(options) if options else None
        self.states = dict(states or {})
        self.writable = writable
        self.limits = {
            "warn_high": warn_high, "alarm_high": alarm_high,
            "warn_low": warn_low, "alarm_low": alarm_low,
        }
        self.description = description
        self.urgent = urgent if urgent is not None else kind != "number"
        self.quiet = quiet  # True: writes are not added to the event log (sticks, continuous controls)
        if kind == "enum" and not self.options:
            raise ValueError(f"enum channel {name!r} needs options")
        if initial is None:
            initial = {"number": 0.0, "bool": False, "text": ""}.get(kind)
            if kind == "enum":
                initial = self.options[0]
        self._value = self._normalize(initial)
        self._limit_level: str | None = None
        self._write_handler: Callable | None = None
        self._interlock: Callable[[Any], str | None] | None = None
        self._lock_reason: str | None = None

    # -- public -----------------------------------------------------------
    @property
    def value(self) -> Any:
        return self._value

    def set(self, value: Any, *, urgent: bool | None = None) -> None:
        """Update from hardware. Thread-safe and cheap; call it as often as you like."""
        self._engine._set(self, value, urgent)

    def interlock(self, fn: Callable[[Any], "str | None"]) -> Callable:
        """Register the interlock for this channel: ``fn(target) -> reason | None``.

        The engine checks it before every UI write (``target`` is the requested value) and,
        for on/off channels, publishes the live reason the switch can't change right now, so
        every control for this channel shows its own lock and why.
        """
        self._interlock = fn
        return fn

    def on_write(self, fn: Callable[[Any], Any]) -> Callable:
        """Register the hardware handler for UI writes to this channel.

        The handler receives the validated value. Return the value actually
        applied (or None to accept as-is), or raise WriteRejected("why").
        """
        self._write_handler = fn
        return fn

    def describe(self) -> dict:
        d = {
            "name": self.name, "kind": self.kind, "label": self.label,
            "unit": self.unit, "group": self.group, "writable": self.writable,
            "fmt": self.fmt, "description": self.description,
        }
        for key in ("min", "max", "step", "precision"):
            if getattr(self, key) is not None:
                d[key] = getattr(self, key)
        if self.log_scale:
            d["log_scale"] = True
        if self.options:
            d["options"] = self.options
        if self.states:
            d["states"] = self.states
        limits = {k: v for k, v in self.limits.items() if v is not None}
        if limits:
            d["limits"] = limits
        if self._interlock is not None:
            d["interlocked"] = True
        return d

    # -- internals ----------------------------------------------------------
    def _normalize(self, v: Any) -> Any:
        if self.kind == "number":
            if v is None:
                return None
            v = float(v)
            return v if math.isfinite(v) else None
        if self.kind == "bool":
            return bool(v)
        if self.kind == "text":
            return "" if v is None else str(v)
        return v  # enum: trusted from hardware

    def _validate_write(self, v: Any) -> Any:
        if self.kind == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise WriteRejected(f"{self.label} needs a number")
            v = float(v)
            if not math.isfinite(v):
                raise WriteRejected(f"{self.label} needs a finite number")
            if self.min is not None and v < self.min:
                raise WriteRejected(f"{self.label} minimum is {self.min:g} {self.unit}".strip())
            if self.max is not None and v > self.max:
                raise WriteRejected(f"{self.label} maximum is {self.max:g} {self.unit}".strip())
            return v
        if self.kind == "bool":
            if not isinstance(v, bool):
                raise WriteRejected(f"{self.label} needs true or false")
            return v
        if self.kind == "enum":
            if v not in self.options:
                raise WriteRejected(f"{self.label} must be one of {', '.join(self.options)}")
            return v
        if not isinstance(v, str) or len(v) > 2000:
            raise WriteRejected(f"{self.label} needs text under 2000 characters")
        return v

    def _check_limits(self) -> tuple[str | None, str | None] | None:
        """Returns (new_level, message) when the limit level changed."""
        if self.kind != "number" or self._value is None:
            return None
        lim, v = self.limits, self._value
        level = None
        if lim["alarm_high"] is not None and v >= lim["alarm_high"]:
            level = "alarm"
        elif lim["alarm_low"] is not None and v <= lim["alarm_low"]:
            level = "alarm"
        elif lim["warn_high"] is not None and v >= lim["warn_high"]:
            level = "warn"
        elif lim["warn_low"] is not None and v <= lim["warn_low"]:
            level = "warn"
        if level == self._limit_level:
            return None
        # hysteresis: only clear/downgrade once 2% back inside the limit
        if self._limit_level and (level is None or (level == "warn" and self._limit_level == "alarm")):
            for key in (("alarm_high", "warn_high") if self._limit_level == "alarm" else ("warn_high",)):
                t = lim[key]
                if t is not None and v > t - abs(t) * 0.02 and key.startswith(self._limit_level):
                    return None
            for key in (("alarm_low",) if self._limit_level == "alarm" else ("warn_low",)):
                t = lim[key]
                if t is not None and v < t + abs(t) * 0.02:
                    return None
        self._limit_level = level
        if level is None:
            return None, None
        fmt = f"{v:.3g}"
        return level, f"{self.label} at {fmt} {self.unit}".strip() + (" (alarm limit)" if level == "alarm" else " (warning limit)")


class Command:
    def __init__(self, name, fn, label, confirm, danger, group, description):
        self.name, self.fn = name, fn
        self.label = label or name.replace("_", " ").title()
        self.confirm, self.danger = confirm, danger
        self.group = group or (name.split(".")[0] if "." in name else "")
        self.description = description
        try:
            self.takes_args = len(inspect.signature(fn).parameters) > 0
        except (TypeError, ValueError):
            self.takes_args = False

    def describe(self) -> dict:
        return {"name": self.name, "label": self.label, "confirm": self.confirm,
                "danger": self.danger, "group": self.group, "description": self.description}


# --------------------------------------------------------------------------
# Connected stations
# --------------------------------------------------------------------------
class Station:
    """One connected UI. Outgoing data is coalesced so a slow link never lags."""

    _ids = itertools.count(1)

    def __init__(self, ws, name: str, addr: str):
        self.ws = ws
        self.id = f"s{next(self._ids)}"
        self.name = name or f"Station {self.id[1:]}"
        self.addr = addr
        self.since = time.time()
        self.last_seen = time.monotonic()
        self._values: dict = {}
        self._writes: dict = {}
        self._queue: deque = deque()
        self._event = asyncio.Event()
        self.op_lock = asyncio.Lock()
        self.closed = False

    def describe(self) -> dict:
        return {"id": self.id, "name": self.name, "addr": self.addr, "since": self.since}

    def push_values(self, values: dict, writes: dict | None) -> None:
        self._values.update(values)
        if writes:
            self._writes.update(writes)
        self._event.set()

    def send(self, msg: dict) -> None:
        self._queue.append(msg)
        self._event.set()

    async def sender(self) -> None:
        dumps = _dumps
        while not self.closed:
            await self._event.wait()
            self._event.clear()
            if self._values:
                msg = {"t": "d", "ts": time.time(), "v": self._values}
                if self._writes:
                    msg["w"] = self._writes
                self._values, self._writes = {}, {}
                await self.ws.send_text(dumps(msg))
            while self._queue:
                await self.ws.send_text(dumps(self._queue.popleft()))


def _dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), allow_nan=False, default=str)


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
class Engine:
    """
    Parameters
    ----------
    name:            Station name shown in every UI.
    control:         "lock" = one station operates at a time, others view.
                     "open" = any station may operate.
    frame_rate:      Max rate (Hz) for coalesced analog telemetry. Switches, modes and writes are
                     sent at once regardless. 30 reads smoothly; 60 is smoother and costs the
                     screen noticeably more CPU.
    app_dir:         The app's folder. Holds layouts/, custom widgets/ and the app's ui_dist/.
                     Defaults to the folder of the script that creates the engine.
    layouts_dir:     Override where UI layouts are stored as JSON.
    watchdog:        Seconds of silence before the operating station loses control.
    history_seconds: Trend history kept for charts on newly connected stations.
    """

    def __init__(
        self,
        name: str = "NexusUI Station",
        *,
        control: str = "lock",
        frame_rate: float = 30.0,
        app_dir: str | Path | None = None,
        layouts_dir: str | Path | None = None,
        watchdog: float = 1.5,
        history_seconds: float = 120.0,
        history_rate: float = 10.0,
    ):
        if control not in ("lock", "open"):
            raise ValueError("control must be 'lock' or 'open'")
        self.name = name
        self.control_mode = control
        # asyncio timers can't fire faster than the platform clock (15.6 ms on Windows + Python 3.11)
        tick = time.get_clock_info("monotonic").resolution
        if 1.0 / frame_rate < tick * 1.05:
            log.warning("frame_rate %.0f Hz is faster than this platform's timer; using %.0f Hz",
                        frame_rate, 1.0 / (tick * 1.05))
            frame_rate = 1.0 / (tick * 1.05)
        self.frame_rate = frame_rate
        if app_dir is None:
            caller = inspect.stack()[1].filename
            app_dir = Path(caller).resolve().parent if Path(caller).exists() else Path.cwd()
        self.app_dir = Path(app_dir).resolve()
        self.layouts_dir = Path(layouts_dir) if layouts_dir else self.app_dir / "layouts"
        self.watchdog = watchdog
        self.history_rate = history_rate
        self._history_len = int(history_seconds * history_rate)

        self.channels: dict[str, Channel] = {}
        self.commands: dict[str, Command] = {}
        self.devices: dict[str, Any] = {}
        self.diagrams: dict[str, Any] = {}
        self.stations: dict[str, Station] = {}
        self.controller: Station | None = None
        self.override = False        # interlock override, owned by the operating station
        self.override_by: str | None = None

        self._lock = threading.Lock()          # guards dirty/alerts/logs
        self._hw_lock = threading.Lock()       # serializes write/command handlers
        self._dirty: dict[str, Any] = {}
        self._dirty_writes: dict[str, dict] = {}
        self._last_write: dict[str, dict] = {}
        self._alerts: dict[str, dict] = {}
        self._alerts_dirty = False
        self._alert_ids = itertools.count(1)
        self._logs: deque = deque(maxlen=300)
        self._new_logs: list = []
        self._history: dict[str, deque] = {}
        self._history_t: deque = deque(maxlen=self._history_len)

        self._loops: list[tuple[Callable, float, str]] = []
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._on_control_lost: list[Callable] = []
        self._on_start: list[Callable] = []
        self._on_stop: list[Callable] = []
        self._aio: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []
        self.started_at = time.time()

    # ------------------------------------------------------------------ API
    def channel(self, name: str, kind: str = "number", **kw) -> Channel:
        """Declare a named value. ``kind`` is number, bool, enum or text, or an I/O shorthand:
        DO / DI (an on/off you set / read) or AO / AI (a value you set / read)."""
        if name in self.channels:
            raise ValueError(f"channel {name!r} already defined")
        if kind.upper() in IO_KINDS:
            kind, writable = IO_KINDS[kind.upper()]
            kw.setdefault("writable", writable)
        ch = Channel(self, name, kind, **kw)
        self.channels[name] = ch
        if kind == "number":
            self._history[name] = deque(maxlen=self._history_len)
        return ch

    def add_device(self, device) -> None:
        if device.id in self.devices:
            raise ValueError(f"device {device.id!r} already defined")
        self.devices[device.id] = device

    def add_diagram(self, diagram) -> None:
        self.diagrams[diagram.id] = diagram

    def __getitem__(self, name: str) -> Channel:
        return self.channels[name]

    def command(self, name: str, *, label: str | None = None, confirm: bool = False,
                danger: bool = False, group: str = "", description: str = ""):
        """Decorator: expose a function as a UI command. ``fn()`` or ``fn(args: dict)``."""
        def deco(fn):
            self.commands[name] = Command(name, fn, label, confirm, danger, group, description)
            return fn
        return deco

    def loop(self, hz: float, name: str | None = None):
        """Decorator: run ``fn(dt)`` at ``hz`` in its own thread, independent of any UI."""
        def deco(fn):
            self._loops.append((fn, hz, name or fn.__name__))
            return fn
        return deco

    def on_control_lost(self, fn):
        """Decorator: called (in a worker thread) when the operating station drops off."""
        self._on_control_lost.append(fn)
        return fn

    def on_start(self, fn):
        self._on_start.append(fn)
        return fn

    def on_stop(self, fn):
        self._on_stop.append(fn)
        return fn

    def update(self, values: dict[str, Any]) -> None:
        for k, v in values.items():
            self.channels[k].set(v)

    def log(self, msg: str, level: str = "info", source: str = "engine") -> None:
        entry = {"ts": time.time(), "level": level, "source": source, "msg": msg}
        with self._lock:
            self._logs.append(entry)
            self._new_logs.append(entry)
        self._poke()

    def alert(self, key: str, msg: str, level: str = "warn", source: str = "engine") -> None:
        """Raise (or refresh) a latched alert. It stays until cleared and acknowledged."""
        now = time.time()
        with self._lock:
            a = self._alerts.get(key)
            if a and a["active"] and a["level"] == level:
                if a["msg"] == msg:
                    return
                a["msg"] = msg
            elif a:
                a.update(level=level, msg=msg, active=True, acked=False, ts=now, count=a["count"] + 1)
            else:
                a = {"id": next(self._alert_ids), "key": key, "level": level, "source": source,
                     "msg": msg, "ts": now, "active": True, "acked": False, "count": 1}
                self._alerts[key] = a
            self._alerts_dirty = True
            self._logs.append(entry := {"ts": now, "level": level, "source": source, "msg": msg})
            self._new_logs.append(entry)
        self._poke(urgent=True)

    def clear_alert(self, key: str) -> None:
        with self._lock:
            a = self._alerts.get(key)
            if not a or not a["active"]:
                return
            a["active"] = False
            a["cleared"] = time.time()
            self._alerts_dirty = True
        self._poke(urgent=True)

    def snapshot(self) -> dict[str, Any]:
        return {n: c._value for n, c in self.channels.items()}

    # ------------------------------------------------------------ internals
    def _set(self, ch: Channel, value: Any, urgent: bool | None, writer: dict | None = None) -> None:
        v = ch._normalize(value)
        limit_change = None
        with self._lock:
            changed = v != ch._value
            ch._value = v
            if changed or writer:
                self._dirty[ch.name] = v
                if writer:
                    self._dirty_writes[ch.name] = writer
                    self._last_write[ch.name] = writer
            limit_change = ch._check_limits() if changed else None
        if limit_change is not None:
            level, msg = limit_change
            if level:
                self.alert(f"limit:{ch.name}", msg, level, source=ch.group or ch.name)
            else:
                self.clear_alert(f"limit:{ch.name}")
        if changed or writer:
            self._poke(urgent=ch.urgent if urgent is None else urgent)

    def _poke(self, urgent: bool = False) -> None:
        if not urgent or self._aio is None or self._wake is None:
            return
        try:
            self._aio.call_soon_threadsafe(self._wake.set)
        except RuntimeError:
            pass  # loop closed during shutdown

    def _flush(self) -> None:
        with self._lock:
            values, self._dirty = self._dirty, {}
            writes, self._dirty_writes = self._dirty_writes, {}
            logs, self._new_logs = self._new_logs, []
            alerts = self._alert_list() if self._alerts_dirty else None
            self._alerts_dirty = False
        stations = list(self.stations.values())
        if values:
            for s in stations:
                s.push_values(values, writes)
        if logs:
            for s in stations:
                s.send({"t": "logs", "list": logs})
        if alerts is not None:
            for s in stations:
                s.send({"t": "alerts", "list": alerts})

    def _alert_list(self) -> list[dict]:
        return sorted(self._alerts.values(), key=lambda a: -a["ts"])

    def _eval_locks(self) -> None:
        """Re-evaluate interlocks of on/off channels and push any change to every station."""
        changed = {}
        for ch in self.channels.values():
            if ch._interlock is None or ch.kind != "bool":
                continue
            try:
                why = ch._interlock(not ch._value)
            except Exception as e:  # a broken interlock must fail safe (locked) and be visible
                why = f"interlock error: {e!r}"
            if why != ch._lock_reason:
                ch._lock_reason = why
                changed[ch.name] = why
        if changed:
            self._broadcast({"t": "locks", "v": changed})

    def _sample_history(self) -> None:
        now = time.time()
        with self._lock:
            self._history_t.append(round(now, 3))
            for name, buf in self._history.items():
                buf.append(self.channels[name]._value)

    def _history_payload(self) -> dict:
        with self._lock:
            return {"t": list(self._history_t),
                    "v": {name: list(buf) for name, buf in self._history.items()}}

    def _control_payload(self) -> dict:
        c = self.controller
        return {"t": "control", "mode": self.control_mode,
                "holder": c.id if c else None, "holder_name": c.name if c else None,
                "override": self.override, "override_by": self.override_by}

    def _broadcast(self, msg: dict) -> None:
        for s in list(self.stations.values()):
            s.send(msg)

    def _broadcast_stations(self) -> None:
        self._broadcast({"t": "stations", "list": [s.describe() for s in self.stations.values()]})

    def hello(self, station: Station) -> dict:
        with self._lock:
            values = {n: c._value for n, c in self.channels.items()}
            alerts = self._alert_list()
            logs = list(self._logs)[-150:]
            writes = dict(self._last_write)
            locks = {n: c._lock_reason for n, c in self.channels.items() if c._lock_reason}
        return {
            "t": "hello", "ts": time.time(),
            "you": station.describe(),
            "engine": {"name": self.name, "control": self.control_mode,
                       "frame_rate": self.frame_rate, "watchdog": self.watchdog,
                       "started_at": self.started_at},
            "channels": [c.describe() for c in self.channels.values()],
            "commands": [c.describe() for c in self.commands.values()],
            "devices": [d.describe() for d in self.devices.values()],
            "diagrams": [d.describe() for d in self.diagrams.values()],
            "values": values, "writes": writes,
            "control": self._control_payload(),
            "stations": [s.describe() for s in self.stations.values()],
            "alerts": alerts, "logs": logs, "locks": locks,
            "history": self._history_payload(),
        }

    # -------------------------------------------------------- station ops
    def _require_control(self, st: Station) -> None:
        if self.control_mode == "lock" and self.controller is not st:
            holder = self.controller.name if self.controller else "nobody"
            raise WriteRejected(f"View only: {holder} has control. Take control to operate.")

    async def handle_message(self, st: Station, msg: dict) -> None:
        st.last_seen = time.monotonic()
        t = msg.get("t")
        if t == "ping":
            st.send({"t": "pong", "id": msg.get("id"), "ct": msg.get("ct"), "st": time.time()})
        elif t in ("write", "cmd"):
            asyncio.get_running_loop().create_task(self._guarded_op(st, msg))
        elif t == "claim":
            self._claim(st, bool(msg.get("force")), msg.get("id"))
        elif t == "release":
            if self.controller is st:
                self._set_controller(None, f"{st.name} released control")
            st.send({"t": "ack", "id": msg.get("id"), "ok": True})
        elif t == "override":
            self._set_override(st, bool(msg.get("on")), msg.get("id"))
        elif t == "ack_alerts":
            ids = msg.get("ids")
            with self._lock:
                for a in self._alerts.values():
                    if ids == "all" or a["id"] in (ids or []):
                        a["acked"] = True
                self._alerts_dirty = True
            self.log(f"{st.name} acknowledged {'all alerts' if ids == 'all' else 'an alert'}", source="alerts")
            self._poke(urgent=True)
        elif t == "clear_alerts":
            with self._lock:
                for k in [k for k, a in self._alerts.items() if not a["active"] and a["acked"]]:
                    del self._alerts[k]
                self._alerts_dirty = True
            self._poke(urgent=True)
        elif t == "rename":
            name = str(msg.get("name", ""))[:40].strip()
            if name:
                st.name = name
                self._broadcast_stations()
                if self.controller is st:
                    self._broadcast(self._control_payload())

    async def _guarded_op(self, st: Station, msg: dict) -> None:
        async with st.op_lock:  # keep one station's operations in order
            rid = msg.get("id")
            try:
                self._require_control(st)
                if msg["t"] == "write":
                    await self._do_write(st, msg)
                else:
                    await self._do_command(st, msg)
                st.send({"t": "ack", "id": rid, "ok": True})
            except WriteRejected as e:
                st.send({"t": "ack", "id": rid, "ok": False, "error": str(e)})
            except Exception as e:  # handler bug: report, never crash the gateway
                log.exception("operation failed")
                self.log(f"{msg.get('ch') or msg.get('name')}: {e!r}", "alarm", "engine")
                st.send({"t": "ack", "id": rid, "ok": False, "error": f"Internal error: {e}"})

    async def _do_write(self, st: Station, msg: dict) -> None:
        ch = self.channels.get(msg.get("ch"))
        if ch is None:
            raise WriteRejected(f"Unknown channel {msg.get('ch')!r}")
        if not ch.writable:
            raise WriteRejected(f"{ch.label} is read-only")
        value = ch._validate_write(msg.get("v"))
        overridden = None
        if ch._interlock:
            why = ch._interlock(value)
            if why and not self.override:
                raise WriteRejected(f"{ch.label} locked: {why}")
            overridden = why
        if ch._write_handler:
            def run():
                with self._hw_lock:
                    return ch._write_handler(value)
            result = await asyncio.to_thread(run)
            if result is not None:
                value = result
        writer = {"by": st.name, "ts": time.time()}
        self._set(ch, value, urgent=True, writer=writer)
        self._flush()  # deliver the new state to every station before the ack
        self._eval_locks()
        shown = f"{value:g}" if isinstance(value, float) else value
        if overridden:
            self.log(f"{st.name} OVERRODE interlock: {ch.label} = {shown} ({overridden})", "alarm", "override")
        elif not ch.quiet:
            self.log(f"{st.name} set {ch.label} = {shown} {ch.unit}".rstrip(), source=ch.group or "write")

    async def _do_command(self, st: Station, msg: dict) -> None:
        cmd = self.commands.get(msg.get("name"))
        if cmd is None:
            raise WriteRejected(f"Unknown command {msg.get('name')!r}")
        args = msg.get("args") or {}

        def run():
            with self._hw_lock:
                return cmd.fn(args) if cmd.takes_args else cmd.fn()
        self.log(f"{st.name} ran {cmd.label}", "warn" if cmd.danger else "info", cmd.group or "command")
        await asyncio.to_thread(run)
        self._flush()
        self._eval_locks()

    def _claim(self, st: Station, force: bool, rid) -> None:
        if self.control_mode == "open" or self.controller is st:
            st.send({"t": "ack", "id": rid, "ok": True})
            return
        if self.controller is not None and not force:
            st.send({"t": "ack", "id": rid, "ok": False, "error": f"{self.controller.name} has control"})
            return
        prev = self.controller
        note = f" (taken from {prev.name})" if prev else ""
        self._set_controller(st, f"{st.name} took control{note}", "warn" if prev else "info")
        st.send({"t": "ack", "id": rid, "ok": True})

    def _set_override(self, st: Station, on: bool, rid=None) -> None:
        if on and self.control_mode == "lock" and self.controller is not st:
            st.send({"t": "ack", "id": rid, "ok": False, "error": "Only the operating station can override interlocks"})
            return
        if on == self.override:
            st.send({"t": "ack", "id": rid, "ok": True})
            return
        self.override = on
        self.override_by = st.name if on else None
        if on:
            self.alert("override", f"INTERLOCK OVERRIDE active ({st.name}). Interlocks are not enforced.",
                       "alarm", "override")
        else:
            self.log(f"{st.name} ended the interlock override", "warn", "override")
            self.clear_alert("override")
        self._broadcast(self._control_payload())
        st.send({"t": "ack", "id": rid, "ok": True})

    def _end_override(self, why: str) -> None:
        if self.override:
            self.override = False
            self.override_by = None
            self.log(f"Interlock override ended: {why}", "warn", "override")
            self.clear_alert("override")

    def _set_controller(self, st: Station | None, why: str, level: str = "info") -> None:
        if st is not self.controller:
            self._end_override("control changed hands")
        self.controller = st
        self._broadcast(self._control_payload())
        self.log(why, level, "control")

    def _lose_control(self, why: str) -> None:
        st = self.controller
        self._set_controller(None, f"{st.name} lost control: {why}", "alarm")
        self.alert("control_lost", f"Operating station {st.name} lost control ({why}). Safe actions ran.",
                   "alarm", "control")
        for fn in self._on_control_lost:
            threading.Thread(target=self._safe_call, args=(fn,), daemon=True).start()

    def _safe_call(self, fn):
        try:
            with self._hw_lock:
                fn()
        except Exception:
            log.exception("on_control_lost handler failed")

    async def connect(self, st: Station) -> None:
        self.stations[st.id] = st
        self._broadcast_stations()
        self.log(f"{st.name} connected from {st.addr}", source="stations")

    async def disconnect(self, st: Station) -> None:
        st.closed = True
        st._event.set()
        self.stations.pop(st.id, None)
        if self.controller is st:
            self._lose_control("disconnected")
        self._broadcast_stations()
        self.log(f"{st.name} disconnected", source="stations")

    # ----------------------------------------------------- lifecycle
    async def _flusher(self) -> None:
        period = 1.0 / self.frame_rate
        hist_period = 1.0 / self.history_rate
        next_hist = time.monotonic()
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), period)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            try:
                self._flush()
                if time.monotonic() >= next_hist:
                    next_hist += hist_period
                    if time.monotonic() > next_hist:
                        next_hist = time.monotonic() + hist_period
                    self._sample_history()
                    self._eval_locks()
            except Exception:
                log.exception("flush failed")

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(0.2)
            c = self.controller
            if c and time.monotonic() - c.last_seen > self.watchdog:
                self._lose_control(f"no heartbeat for {self.watchdog:g}s")

    def _run_hw_loop(self, fn, hz, name):
        period = 1.0 / hz
        last = time.perf_counter()
        next_t = last + period
        errors = 0
        while not self._stop.is_set():
            now = time.perf_counter()
            dt, last = now - last, now
            try:
                fn(dt)
                errors = 0
            except Exception as e:
                errors += 1
                if errors in (1, 10, 100) or errors % 1000 == 0:
                    log.exception("loop %s failed", name)
                    self.alert(f"loop:{name}", f"Loop {name} raised {e!r} ({errors}x)", "alarm", "engine")
            next_t += period
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            elif delay < -5 * period:
                next_t = time.perf_counter()  # overrun: resync instead of bursting

    async def startup(self) -> None:
        """Called by the gateway lifespan. Starts flusher, watchdog and hardware loops."""
        _hi_res_timers(True)
        for d in self.diagrams.values():
            missing = sorted(c for c in d.channels() if c not in self.channels)
            if missing:
                log.warning("diagram %s references unknown channels: %s", d.id, ", ".join(missing))
        self._aio = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._stop.clear()
        for fn in self._on_start:
            fn()
        for fn, hz, name in self._loops:
            t = threading.Thread(target=self._run_hw_loop, args=(fn, hz, name), name=f"loop:{name}", daemon=True)
            t.start()
            self._threads.append(t)
        self._tasks = [self._aio.create_task(self._flusher()), self._aio.create_task(self._watchdog())]
        self.log(f"{self.name} engine started", source="engine")

    async def shutdown(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for fn in self._on_stop:
            try:
                fn()
            except Exception:
                log.exception("on_stop handler failed")
        for t in self._threads:
            t.join(timeout=1)
        self._threads.clear()
        _hi_res_timers(False)

    @property
    def app(self):
        from .gateway import create_app
        if not hasattr(self, "_app"):
            self._app = create_app(self)
        return self._app

    def run(self, host: str | None = None, port: int | None = None, *, desktop: bool | None = None,
            title: str | None = None, log_level: str = "warning") -> None:
        """Open the station in its own window, or serve it to browsers.

        By default it opens a standalone window that is private to this computer: nothing to
        type into a browser, no port to choose, not reachable from the network. Where no window
        can be opened (pywebview missing, or Linux without a display) it serves browsers instead.

        ``desktop=False`` serves browsers at ``http://<this-computer>:8000``, for other devices
        or a machine without a screen. ``host="0.0.0.0"`` with a ``port`` gives both: the window
        here and browsers elsewhere.
        """
        import socket

        import uvicorn
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        desktop, host, port = _run_target(host, port, desktop)
        try:
            sock = socket.create_server((host, port))
        except OSError as e:
            sys.exit(f"[{self.name}] could not start on port {port} ({e.strerror}). Try another --port.")
        port = sock.getsockname()[1]
        config = uvicorn.Config(self.app, host=host, port=port, log_level=log_level, ws_ping_interval=None)
        server = uvicorn.Server(config)
        if not desktop:
            print(f"[{self.name}] UI at http://localhost:{port}  (other stations: http://<this-ip>:{port})", flush=True)
            server.run(sockets=[sock])
            return
        from .desktop import open_window
        if host == "127.0.0.1":
            print(f"[{self.name}] running in its own window. For a browser or another device, start it with --browser.", flush=True)
        else:
            print(f"[{self.name}] running in its own window; other stations: http://<this-ip>:{port}", flush=True)
        th = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        th.start()
        while not server.started and th.is_alive():
            time.sleep(0.02)
        if not server.started:  # don't open a window onto nothing
            sys.exit(f"[{self.name}] could not start. See the error above.")
        open_window(f"http://127.0.0.1:{port}", title or self.name)
        server.should_exit = True
        th.join(timeout=3)


def _run_target(host: str | None, port: int | None, desktop: bool | None) -> tuple[bool, str, int]:
    """Fill in run()'s defaults: a private window when one can be opened, otherwise a browser server."""
    if desktop is None:
        has_display = sys.platform != "linux" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        desktop = has_display and importlib.util.find_spec("webview") is not None
    if desktop:
        return True, host or "127.0.0.1", port or 0     # port 0: the system picks a free one
    return False, host or "0.0.0.0", port or 8000


def _hi_res_timers(on: bool) -> None:
    """Windows timers default to ~15.6 ms ticks, which makes 60 Hz updates stutter."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        (ctypes.windll.winmm.timeBeginPeriod if on else ctypes.windll.winmm.timeEndPeriod)(1)
    except Exception:
        pass
