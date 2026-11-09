"""
nexusui.widget
---------------
Every widget is a folder:

    widgets/<type>/
        backend.py   Python side. Declares SPEC (what the widget is: sizes,
                     accepted data, settings). Device widgets also define a
                     Device subclass: the channels, commands, safety checks
                     and simulator for one piece of hardware.
        ui.tsx       Browser side. How the widget looks and behaves.

The engine never imports UI code and the UI never touches hardware. They meet
only through channel names, which the layout file binds together.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .engine import Channel, Engine, WriteRejected

# Layout grid: 24 columns wide, rows of GRID_ROW_PX pixels. The grid is fine
# enough that widgets resize freely; widgets float up to fill gaps.
GRID_COLS = 24
GRID_ROW_PX = 10

# Size presets in grid cells (w, h). Like iOS widgets, each widget lists the
# presets it has a purpose-made design for. Any size in between is allowed;
# the UI picks the largest preset design that fits the current box.
SIZES: dict[str, tuple[int, int]] = {
    "s": (4, 10),    # small square
    "m": (8, 10),    # medium, wide
    "l": (8, 21),    # large square
    "t": (4, 21),    # tall
    "xl": (16, 21),  # extra large, wide
}


@dataclass
class WidgetSpec:
    type: str
    label: str
    description: str = ""
    category: str = "General"          # "General", "Control", "Trend", "Device"
    sizes: list[str] = field(default_factory=lambda: ["s"])
    default_size: str | None = None
    min_w: int = 3                       # smallest allowed box, in grid cells
    min_h: int = 5
    bind: str = "none"                   # "none" | "channel" | "channels" | "command" | "device"
    accepts: list[str] = field(default_factory=list)   # channel kinds, e.g. ["number"]
    writable_only: bool = False
    settings: list[dict] = field(default_factory=list)  # extra options shown in the inspector

    def describe(self) -> dict:
        d = asdict(self)
        d["default_size"] = self.default_size or self.sizes[0]
        d["size_cells"] = {k: SIZES[k] for k in self.sizes if k in SIZES}
        return d


def setting(key: str, label: str, kind: str = "text", default: Any = None, **kw) -> dict:
    """Describe one inspector field. kind: text | number | bool | select."""
    return {"key": key, "label": label, "kind": kind, "default": default, **kw}


class Device:
    """
    Base class for device widgets. A device owns a set of channels named
    ``<id>.<role>`` and the hardware logic behind them.

    Subclass it in ``widgets/<type>/backend.py``, set ``widget = "<type>"``,
    create channels with ``self.ch`` and commands with ``self.cmd``. Put the
    real driver calls in write handlers and ``poll``; put the simulator in
    ``simulate``. The UI file for the same folder renders the device card.
    """

    widget: str = ""

    def __init__(self, engine: Engine, id: str, label: str | None = None, *, sim: bool = True):
        if not self.widget:
            raise TypeError("Device subclasses must set the widget type")
        self.engine = engine
        self.id = id
        self.label = label or id.replace("_", " ").title()
        self.sim = sim
        self.roles: dict[str, str] = {}
        self.command_roles: dict[str, str] = {}
        engine.add_device(self)

    def ch(self, role: str, kind: str = "number", **kw) -> Channel:
        kw.setdefault("group", self.id)
        kw.setdefault("label", f"{self.label} {role.replace('_', ' ')}")
        c = self.engine.channel(f"{self.id}.{role}", kind, **kw)
        self.roles[role] = c.name
        return c

    def cmd(self, role: str, fn: Callable, **kw) -> None:
        kw.setdefault("group", self.id)
        kw.setdefault("label", role.replace("_", " ").title())
        name = f"{self.id}.{role}"
        self.engine.command(name, **kw)(fn)
        self.command_roles[role] = name

    def alert(self, key: str, msg: str, level: str = "warn") -> None:
        self.engine.alert(f"{self.id}:{key}", f"{self.label}: {msg}", level, source=self.id)

    def clear(self, key: str) -> None:
        self.engine.clear_alert(f"{self.id}:{key}")

    def step(self, dt: float) -> None:
        """Called from the station's hardware loop."""
        if self.sim:
            self.simulate(dt)
        else:
            self.poll(dt)

    def simulate(self, dt: float) -> None:
        pass

    def poll(self, dt: float) -> None:
        """Read the real hardware here."""

    def describe(self) -> dict:
        return {"id": self.id, "type": self.widget, "label": self.label,
                "channels": self.roles, "commands": self.command_roles, "sim": self.sim}


def discover_widgets(app_dir: str | Path | None = None) -> dict[str, WidgetSpec]:
    """Collect SPECs from framework widgets, then from the app's own widgets/ folder.

    An app widget with the same name as a framework widget replaces it, so an
    app can customize a premade device without forking the framework.
    """
    import sys
    from . import widgets as pkg
    specs: dict[str, WidgetSpec] = {}
    sources = [(Path(pkg.__file__).parent, f"{pkg.__name__}.{{}}.backend")]
    if app_dir and (Path(app_dir) / "widgets").is_dir():
        root = str(Path(app_dir).resolve())
        if root not in sys.path:
            sys.path.insert(0, root)
        sources.append((Path(app_dir) / "widgets", "widgets.{}.backend"))
    for folder, modname in sources:
        for sub in sorted(folder.iterdir()):
            if not (sub / "backend.py").exists():
                continue
            mod = importlib.import_module(modname.format(sub.name))
            spec = getattr(mod, "SPEC", None)
            if isinstance(spec, WidgetSpec):
                specs[spec.type] = spec
    return specs


__all__ = ["WidgetSpec", "Device", "SIZES", "GRID_COLS", "GRID_ROW_PX", "setting", "discover_widgets", "WriteRejected"]
