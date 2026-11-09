"""
Positioning servo for steering, a gimbal, a rudder or a flap: commanded position,
a per-servo travel limit, position readback and drive voltage.
"""
from __future__ import annotations

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="servo", label="Servo", category="Device",
    description="Positioning servo: commanded position, travel limit, readback, park.",
    sizes=["s", "m", "t"], default_size="t", bind="device",
)

STATES = {"PARKED": "off", "MOVING": "info", "HOLDING": "active"}


class Servo(Device):
    widget = "servo"

    def __init__(self, engine, id, label=None, *, slew=120.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.slew = slew   # % of travel per second
        self.command_pct = self.ch("command", unit="%", min=0, max=100, step=0.5, precision=1,
                                   writable=True, label=f"{self.label} position")
        self.limit = self.ch("limit", unit="%", min=0, max=100, step=1, precision=0,
                             writable=True, initial=100, label=f"{self.label} travel limit")
        self.position = self.ch("position", unit="%", precision=1)
        self.drive = self.ch("drive", unit="V", precision=2)
        self.state = self.ch("state", "enum", options=list(STATES), states=STATES)
        self.command_pct.on_write(self._write_cmd)
        self.limit.on_write(self._write_limit)
        self.cmd("park", self.park, label="Park")

    def _write_cmd(self, v):
        if v > self.limit.value:
            raise WriteRejected(f"{self.label}: travel limit is {self.limit.value:g} %")
        return v

    def _write_limit(self, v):
        if self.command_pct.value > v:
            self.command_pct.set(v)
        return v

    def park(self):
        self.command_pct.set(0.0)

    def simulate(self, dt):
        target = min(self.command_pct.value, self.limit.value)
        pos = self.position.value or 0.0
        step = max(-self.slew * dt, min(self.slew * dt, target - pos))
        pos += step
        self.position.set(round(pos, 3))
        self.drive.set(pos / 20.0)
        self.state.set("PARKED" if pos < 0.2 else "MOVING" if abs(target - pos) > 0.2 else "HOLDING")
