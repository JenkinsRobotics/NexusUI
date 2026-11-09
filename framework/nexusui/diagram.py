"""
nexusui.diagram
---------------
Live system diagrams, described in Python and drawn by the ``diagram`` widget.

    d = Diagram(eng, "power", "Power and Drive", width=1000, height=420)
    d.vessel("pack", 60, 120, 240, 160, "Battery", value="batt.soc", state="batt.state")
    d.valve("main", 380, 200, "rover.main_power", "Main power", lock="rover.estop")
    d.equipment("left", 520, 110, 150, 80, "Left motor", kind="motor", on="ml.on",
                state="ml.status", values=["ml.rpm"])
    d.pipe((300, 200), (520, 150), when=["rover.main_power"], kind="power")

Coordinates are diagram units; the widget scales the whole drawing to fit.
A link animates while every channel in ``when`` is truthy (numbers > 0); pass a
list of groups to animate while any one group is all truthy.
Switches and equipment with a writable ``on``/``ch`` channel are clickable.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from .engine import Engine


class Diagram:
    def __init__(self, engine: Engine, id: str, title: str, *, width: int = 1000, height: int = 500):
        self.engine, self.id, self.title = engine, id, title
        self.width, self.height = width, height
        self.elements: list[dict] = []
        engine.add_diagram(self)

    def _add(self, kind: str, **kw) -> "Diagram":
        self.elements.append({"kind": kind, **{k: v for k, v in kw.items() if v is not None}})
        return self

    def vessel(self, id: str, x: float, y: float, w: float, h: float, label: str, *,
               value: str | None = None, state: str | None = None, glow: str | None = None,
               values: Sequence[str] = ()) -> "Diagram":
        """A large unit: a vehicle, a tank, a pack. ``glow`` = bool channel that lights it up while true."""
        return self._add("vessel", id=id, x=x, y=y, w=w, h=h, label=label, value=value, state=state,
                         glow=glow, values=list(values))

    def equipment(self, id: str, x: float, y: float, w: float, h: float, label: str, *,
                  kind: str = "box", on: str | None = None, state: str | None = None,
                  values: Sequence[str] = (), sub: str | None = None) -> "Diagram":
        """Motor, pump, sensor or any block. kind: box | pump | motor (a pump shows a lamp, a motor a spinning rotor)."""
        return self._add("equipment", id=id, x=x, y=y, w=w, h=h, label=label, type=kind, on=on,
                         state=state, values=list(values), sub=sub)

    def valve(self, id: str, x: float, y: float, ch: str, label: str | None = None, *,
              orient: str = "h", lock: str | None = None, label_pos: str = "right") -> "Diagram":
        """On/off switch or valve (bool channel), or a proportional one (number channel, 0-100 %)."""
        return self._add("valve", id=id, x=x, y=y, ch=ch, label=label, orient=orient, lock=lock,
                         label_pos=label_pos)

    def gauge(self, id: str, x: float, y: float, ch: str, tag: str) -> "Diagram":
        """Instrument bubble with a short tag and its live reading."""
        return self._add("gauge", id=id, x=x, y=y, ch=ch, tag=tag)

    def pipe(self, *points: tuple[float, float], when: Iterable | None = None,
             kind: str = "power") -> "Diagram":
        """Polyline link. kind: power | data | liquid | signal. Animates in point order while active.

        when=["a", "b"]                 flows while a AND b are on
        when=[["a", "b"], ["a", "c"]]   flows while (a AND b) OR (a AND c)
        """
        groups = None
        if when:
            when = list(when)
            groups = [list(g) for g in when] if not isinstance(when[0], str) else [when]
        return self._add("pipe", points=[list(p) for p in points], when=groups, type=kind)

    def text(self, x: float, y: float, text: str, *, size: int = 12, anchor: str = "start") -> "Diagram":
        return self._add("text", x=x, y=y, text=text, size=size, anchor=anchor)

    def channels(self) -> set[str]:
        refs: set[str] = set()
        for e in self.elements:
            for key in ("value", "state", "glow", "on", "ch", "lock"):
                if e.get(key):
                    refs.add(e[key])
            refs.update(e.get("values") or [])
            for group in e.get("when") or []:
                refs.update(group)
        return refs

    def describe(self) -> dict:
        return {"id": self.id, "title": self.title, "width": self.width, "height": self.height,
                "elements": self.elements}
