"""
nexusui command line

    nexusui new <name>            scaffold apps/<name> with a station, layouts/ and widgets/
    nexusui build [app_dir]       build the UI (framework default, or an app with custom widgets)
    nexusui station [url]         open a station in a desktop window
    nexusui widgets [app_dir]     list the widgets an app can use
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent          # framework/nexusui
REPO = FRAMEWORK.parent.parent                        # repo root (package.json, vite.config.ts)


def _node_bin() -> list[str]:
    """npx from PATH, or the portable Node in .tools/node."""
    local = REPO / ".tools" / "node"
    if (local / "node.exe").exists() or (local / "bin" / "node").exists():
        os.environ["PATH"] = f"{local}{os.pathsep}{local / 'bin'}{os.pathsep}{os.environ['PATH']}"
    npx = shutil.which("npx")
    if not npx:
        sys.exit("Node.js not found. Install Node 20+ or unpack it into .tools/node.")
    return [npx]


def build(app_dir: str | None) -> None:
    if not (REPO / "vite.config.ts").exists():
        sys.exit(f"Build needs the source checkout (vite.config.ts not found in {REPO}).")
    env = dict(os.environ)
    if app_dir:
        app = Path(app_dir).resolve()
        if not app.is_dir():
            sys.exit(f"No app folder at {app}")
        env["NEXUSUI_APP"] = str(app)
        print(f"Building UI for {app.name} (framework + {app.name}/widgets) -> {app / 'ui_dist'}")
    else:
        env.pop("NEXUSUI_APP", None)
        print(f"Building framework UI -> {FRAMEWORK / 'ui_dist'}")
    npx = _node_bin()
    if not (REPO / "node_modules").exists():
        subprocess.run([shutil.which("npm") or "npm", "install"], cwd=REPO, check=True, shell=sys.platform == "win32")
    subprocess.run(npx + ["vite", "build"], cwd=REPO, env=env, check=True, shell=sys.platform == "win32")


APP_TEMPLATE = '''"""
{title}
{underline}
Backend for this app. The screen layout lives in layouts/*.json and is
edited from the UI (Edit layout). Custom widgets go in widgets/<type>/.

Run:  python {rel}/app.py             opens in its own window
      python {rel}/app.py --browser   then open http://localhost:8000, from any device
"""
import argparse

from nexusui import Engine
from nexusui.widgets.motor.backend import Motor   # premade device from the framework

eng = Engine("{title}", control="lock")

temp = eng.channel("demo.temp", label="Temperature", unit="°C", precision=1, warn_high=80, alarm_high=95)
heater = eng.channel("demo.heater", "bool", label="Heater", writable=True)
setpoint = eng.channel("demo.setpoint", label="Setpoint", unit="°C", min=20, max=90, writable=True, initial=50)
fan = Motor(eng, "fan1", "Fan", full_rpm=3000)


@eng.command("demo.all_off", label="All Off", danger=True)
def all_off():
    heater.set(False)
    fan.on.set(False)


@eng.on_control_lost
def safe():
    all_off()


@eng.loop(hz=50)
def physics(dt):
    t = temp.value
    target = setpoint.value if heater.value else 22.0
    temp.set(t + (target - t) * dt / 8)
    fan.step(dt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true", help="serve browsers on the network instead of opening a window")
    ap.add_argument("--port", type=int)
    a = ap.parse_args()
    eng.run(port=a.port, desktop=False if a.browser else None)
'''

WIDGET_BACKEND = '''"""Custom widget for this app. Declares what the widget is; ui.tsx draws it."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="{name}", label="{label}", category="General",
    description="App-specific widget. Edit ui.tsx to change how it looks.",
    sizes=["s", "m"], bind="channel", accepts=["number"],
)
'''

WIDGET_UI = '''import {{ Title, Unbound, Value, type WidgetProps }} from "@station/kit";

export default function {comp}({{ item }}: WidgetProps) {{
  if (!item.bind) return <Unbound />;
  return (
    <div className="stat">
      <Title>{{item.title || "{label}"}}</Title>
      <Value ch={{item.bind}} className="huge" />
    </div>
  );
}}
'''


def new(name: str, parent: str) -> None:
    app = Path(parent) / name
    if app.exists():
        sys.exit(f"{app} already exists")
    (app / "layouts").mkdir(parents=True)
    w = app / "widgets" / f"{name}_readout"
    w.mkdir(parents=True)
    title = name.replace("_", " ").replace("-", " ").title()
    (app / "app.py").write_text(APP_TEMPLATE.format(title=title, underline="=" * len(title),
                                                    rel=app.as_posix()), "utf-8")
    comp = "".join(p.title() for p in f"{name}_readout".replace("-", "_").split("_"))
    (w / "backend.py").write_text(WIDGET_BACKEND.format(name=w.name, label=f"{title} Readout"), "utf-8")
    (w / "ui.tsx").write_text(WIDGET_UI.format(comp=comp, label=f"{title} Readout"), "utf-8")
    print(f"Created {app}")
    print(f"  python {app.as_posix()}/app.py           run it (framework UI)")
    print(f"  nexusui build {app.as_posix()}           include the custom widget in this app's UI")


def widgets(app_dir: str | None) -> None:
    from .widget import discover_widgets
    for spec in discover_widgets(app_dir).values():
        print(f"{spec.type:14} {spec.category:8} sizes={','.join(spec.sizes):12} {spec.description}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="nexusui", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="build the station UI")
    b.add_argument("app_dir", nargs="?")
    n = sub.add_parser("new", help="scaffold a new app")
    n.add_argument("name")
    n.add_argument("--dir", default="apps")
    s = sub.add_parser("station", help="open a desktop station window")
    s.add_argument("url", nargs="?", default="http://localhost:8000")
    s.add_argument("--fullscreen", action="store_true")
    w = sub.add_parser("widgets", help="list available widgets")
    w.add_argument("app_dir", nargs="?")
    a = p.parse_args(argv)
    if a.cmd == "build":
        build(a.app_dir)
    elif a.cmd == "new":
        new(a.name, a.dir)
    elif a.cmd == "station":
        from .desktop import open_window
        open_window(a.url, fullscreen=a.fullscreen)
    elif a.cmd == "widgets":
        widgets(a.app_dir)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
