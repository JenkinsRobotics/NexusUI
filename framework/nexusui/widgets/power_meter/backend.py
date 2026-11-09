"""
Electrical power meter on a supply bus: watts and bus voltage, with a
calibration factor and a zero.

Station logic sets ``true_w`` and ``true_v``.
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="power_meter", label="Power Meter", category="Device",
    description="Power meter card: watts, bus voltage, calibration, zero.",
    sizes=["s", "m", "t"], default_size="s", bind="device",
)


class PowerMeter(Device):
    widget = "power_meter"

    def __init__(self, engine, id, label=None, *, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.true_w = 0.0     # station logic sets the power drawn
        self.true_v = 0.0     # and the bus voltage
        self._zero_w = random.uniform(0.2, 0.8)
        self.watts = self.ch("watts", unit="W", precision=1, label=f"{self.label} power")
        self.volts = self.ch("volts", unit="V", precision=2, label=f"{self.label} bus")
        self.scale = self.ch("scale", unit="%", min=90, max=110, step=0.1, precision=1,
                             writable=True, initial=100.0, label=f"{self.label} calibration")
        self.zeroed = self.ch("zeroed", "bool", label=f"{self.label} zeroed")
        self.cmd("zero_cal", self._zero, label="Zero Calibrate")

    def _zero(self):
        if self.true_w > 0.5:
            raise WriteRejected(f"{self.label}: switch the load off before zeroing")
        self._zero_w = 0.0
        self.zeroed.set(True)

    def simulate(self, dt):
        w = (self.true_w + self._zero_w) * self.scale.value / 100
        self.watts.set(max(0.0, w * (1 + random.gauss(0, 0.002))))
        self.volts.set(self.true_v + random.gauss(0, 0.005) if self.true_v else 0.0)
