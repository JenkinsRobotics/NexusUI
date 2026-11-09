"""
nexusui.gateway
----------------
Network edge of the engine: one WebSocket per station plus a small REST API
for widget specs and layouts. Serves the prebuilt UI so any browser or the
desktop shell can connect with nothing but a URL.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from .engine import Engine, Station

FRAMEWORK_UI = Path(__file__).parent / "ui_dist"
LAYOUT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_LAYOUT_BYTES = 1_000_000


def create_app(engine: Engine) -> Starlette:
    from .widget import discover_widgets
    specs = discover_widgets(engine.app_dir)
    # An app with custom widgets ships its own build; otherwise use the framework's.
    app_ui = engine.app_dir / "ui_dist"
    ui_dir = app_ui if (app_ui / "index.html").exists() else FRAMEWORK_UI
    custom = [p.parent.name for p in (engine.app_dir / "widgets").glob("*/ui.tsx")] if (engine.app_dir / "widgets").is_dir() else []
    if custom and ui_dir == FRAMEWORK_UI:
        import logging
        logging.getLogger("nexusui").warning(
            "App has custom widgets %s but no ui_dist build. Run: nexusui build %s", custom, engine.app_dir)

    # ---------------------------------------------------------- websocket
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        name = ws.query_params.get("name", "")[:40].strip()
        addr = f"{ws.client.host}" if ws.client else "?"
        st = Station(ws, name, addr)
        await ws.send_text(json.dumps(engine.hello(st), separators=(",", ":"), default=str))
        await engine.connect(st)
        import asyncio
        sender = asyncio.get_running_loop().create_task(st.sender())
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    await engine.handle_message(st, msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            await engine.disconnect(st)

    # ---------------------------------------------------------- REST
    async def info(_: Request):
        return JSONResponse({"name": engine.name, "control": engine.control_mode,
                             "stations": len(engine.stations), "uptime": time.time() - engine.started_at})

    async def widgets(_: Request):
        from .widget import GRID_COLS, GRID_ROW_PX
        return JSONResponse({"widgets": [s.describe() for s in specs.values()],
                             "grid": {"cols": GRID_COLS, "row_px": GRID_ROW_PX}})

    async def list_layouts(_: Request):
        engine.layouts_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for p in sorted(engine.layouts_dir.glob("*.json")):
            with contextlib.suppress(Exception):
                items.append({"name": p.stem, "title": json.loads(p.read_text("utf-8")).get("title", p.stem),
                              "mtime": p.stat().st_mtime})
        default = "default" if any(i["name"] == "default" for i in items) else (items[0]["name"] if items else "default")
        return JSONResponse({"layouts": items, "default": default})

    async def get_layout(req: Request):
        name = req.path_params["name"]
        if not LAYOUT_NAME.match(name):
            return JSONResponse({"error": "bad layout name"}, 400)
        p = engine.layouts_dir / f"{name}.json"
        if p.exists():
            return JSONResponse(json.loads(p.read_text("utf-8")))
        if name == "default":
            return JSONResponse(auto_layout(engine))
        return JSONResponse({"error": "not found"}, 404)

    async def put_layout(req: Request):
        name = req.path_params["name"]
        if not LAYOUT_NAME.match(name):
            return JSONResponse({"error": "Layout names use letters, digits, - and _ only"}, 400)
        body = await req.body()
        if len(body) > MAX_LAYOUT_BYTES:
            return JSONResponse({"error": "layout too large"}, 413)
        try:
            data = json.loads(body)
            assert isinstance(data, dict) and isinstance(data.get("tabs"), list)
        except Exception:
            return JSONResponse({"error": "layout must be a JSON object with a tabs list"}, 400)
        data["version"] = 1
        data["saved_at"] = time.time()
        engine.layouts_dir.mkdir(parents=True, exist_ok=True)
        path = engine.layouts_dir / f"{name}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), "utf-8")
        os.replace(tmp, path)
        by = req.headers.get("x-station-name", "A station")[:40]
        engine.log(f"{by} saved layout '{name}'", source="layout")
        engine._broadcast({"t": "layout", "name": name, "by": by, "station": req.headers.get("x-station-id")})
        return JSONResponse({"ok": True})

    async def delete_layout(req: Request):
        name = req.path_params["name"]
        p = engine.layouts_dir / f"{name}.json"
        if not LAYOUT_NAME.match(name) or not p.exists():
            return JSONResponse({"error": "not found"}, 404)
        p.unlink()
        engine._broadcast({"t": "layout", "name": name, "deleted": True})
        return JSONResponse({"ok": True})

    async def no_ui(_: Request):
        return HTMLResponse(
            "<h2>NexusUI UI is not built</h2><p>Run <code>nexusui build</code> "
            "in the repository root.</p>", 503)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        await engine.startup()
        try:
            yield
        finally:
            await engine.shutdown()

    routes = [
        WebSocketRoute("/ws", ws_endpoint),
        Route("/api/info", info),
        Route("/api/widgets", widgets),
        Route("/api/layouts", list_layouts),
        Route("/api/layouts/{name}", get_layout, methods=["GET"]),
        Route("/api/layouts/{name}", put_layout, methods=["PUT"]),
        Route("/api/layouts/{name}", delete_layout, methods=["DELETE"]),
    ]
    if (ui_dir / "index.html").exists():
        routes.append(Mount("/", StaticFiles(directory=ui_dir, html=True)))
    else:
        routes.append(Route("/", no_ui))
    return Starlette(routes=routes, lifespan=lifespan)


def auto_layout(engine: Engine) -> dict:
    """A starting layout when none is saved: devices first, then loose channels."""
    from .widget import GRID_COLS, SIZES
    widgets, x, y, row_h, n = [], 0, 0, 0, 0

    def place(item, size):
        nonlocal x, y, row_h, n
        w, h = SIZES.get(size, SIZES["l"]) if isinstance(size, str) else size
        if x + w > GRID_COLS:
            x, y, row_h = 0, y + row_h, 0
        n += 1
        widgets.append({"i": f"w{n}", "x": x, "y": y, "w": w, "h": h, **item})
        x += w
        row_h = max(row_h, h)

    owned = set()
    for d in engine.devices.values():
        owned.update(d.roles.values())
        owned.update(d.command_roles.values())
        place({"type": d.widget, "device": d.id, "title": d.label}, "t")
    for c in engine.channels.values():
        if c.name in owned:
            continue
        if c.kind == "bool":
            place({"type": "toggle" if c.writable else "indicator", "bind": c.name, "size": "s"}, "s")
        elif c.kind == "enum":
            place({"type": "mode" if c.writable else "stat", "bind": c.name, "size": "m"}, "m")
        elif c.kind == "number" and c.writable:
            place({"type": "slider", "bind": c.name, "size": "m"}, "m")
        else:
            place({"type": "stat", "bind": c.name, "size": "s"}, "s")
    for cmd in engine.commands.values():
        if cmd.name not in owned:
            place({"type": "button", "command": cmd.name, "size": "s"}, "s")
    return {"version": 1, "cols": GRID_COLS, "title": engine.name, "tabs": [{"id": "main", "title": "Main", "widgets": widgets}]}
