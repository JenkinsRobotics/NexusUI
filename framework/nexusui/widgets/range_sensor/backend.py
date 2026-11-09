"""
Active range sensor (lidar or sonar): emitter on/off with protection, range and
signal strength. The emitter is refused while the sensor is blocked and is
switched off if it becomes blocked.

Station logic sets ``true_range`` (what is in front of the sensor) and
``blocked`` (a reason the emitter may not fire, or None).
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec

SPEC = WidgetSpec(
    type="range_sensor", label="Range Sensor", category="Device",
    description="Lidar or sonar card: emitter on/off with protection, range, signal strength.",
    sizes=["s", "m", "t"], default_size="m", bind="device",
)

STATES = {"OFF": "off", "MEASURING": "ok", "OUT OF RANGE": "info", "PROTECT": "alarm"}


class RangeSensor(Device):
    widget = "range_sensor"

    def __init__(self, engine, id, label=None, *, max_range=40.0, warn_below=None, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.max_range = max_range
        self.true_range = max_range      # station logic sets what the sensor sees
        self.blocked: str | None = None  # station logic: reason the emitter may not fire
        self.emit = self.ch("emit", "bool", writable=True, label=f"{self.label} emitter")
        self.range = self.ch("range", unit="m", precision=2, min=0, max=max_range, warn_low=warn_below,
                             label=f"{self.label} range")
        self.signal = self.ch("signal", unit="%", precision=0, min=0, max=100, label=f"{self.label} signal")
        self.state = self.ch("state", "enum", options=list(STATES), states=STATES)
        self.emit.on_write(self._write_emit)
        self.emit.interlock(lambda on: self.blocked if on else None)

    def _write_emit(self, v):
        if v:
            self.clear("protect")
        return v

    def simulate(self, dt):
        if self.emit.value and self.blocked:
            self.emit.set(False)
            self.state.set("PROTECT")
            self.alert("protect", f"emitter switched off: {self.blocked}", "warn")
        if not self.emit.value:
            self.range.set(None)
            self.signal.set(0.0)
            if self.state.value != "PROTECT":
                self.state.set("OFF")
            return
        r = self.true_range * (1 + random.gauss(0, 0.004))
        if r >= self.max_range:
            self.state.set("OUT OF RANGE")
            self.range.set(None)
            self.signal.set(2.0 + random.random())
            return
        self.state.set("MEASURING")
        self.range.set(max(0.0, r))
        self.signal.set(max(3.0, min(100.0, 100.0 * (1 - r / self.max_range) ** 0.6 + random.gauss(0, 0.6))))
