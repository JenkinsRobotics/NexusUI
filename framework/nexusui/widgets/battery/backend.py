"""
Battery pack: state of charge, voltage, current, temperature and time remaining,
with low and critical thresholds.

Station logic sets ``load_w`` (power being drawn) and ``charge_w`` (charger power).
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="battery", label="Battery", category="Device",
    description="Battery card: charge level, time remaining, voltage, current, temperature, swap.",
    sizes=["s", "m", "t"], default_size="t", bind="device",
)

STATES = {"IDLE": "off", "DISCHARGING": "ok", "CHARGING": "info", "LOW": "warn", "CRITICAL": "alarm"}


class Battery(Device):
    widget = "battery"

    def __init__(self, engine, id, label=None, *, capacity_wh=500.0, cells=6, low=25.0, critical=12.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.capacity_wh = capacity_wh
        self.cells = cells
        self.load_w = 0.0       # station logic: power being drawn
        self.charge_w = 0.0     # station logic: charger power
        self.soc = self.ch("soc", unit="%", precision=0, min=0, max=100, warn_low=low, alarm_low=critical,
                           initial=100.0, label=f"{self.label} charge")
        self.voltage = self.ch("voltage", unit="V", precision=2)
        self.current = self.ch("current", unit="A", precision=1)
        self.temp = self.ch("temp", unit="°C", precision=1, initial=24.0, warn_high=50, alarm_high=60)
        self.remaining = self.ch("remaining", unit="min", precision=0, label=f"{self.label} time remaining")
        self.state = self.ch("state", "enum", options=list(STATES), states=STATES)
        self.cmd("swap", self._swap, label="Swap Battery", description="Fit a full pack. The load must be off.")

    @property
    def low(self) -> bool:
        return self.state.value in ("LOW", "CRITICAL")

    @property
    def critical(self) -> bool:
        return self.state.value == "CRITICAL"

    def _swap(self):
        if self.load_w > self.capacity_wh * 0.05:
            raise WriteRejected(f"{self.label}: switch the load off before swapping")
        self.soc.set(100.0)

    def simulate(self, dt):
        net_w = self.load_w - self.charge_w
        soc = max(0.0, min(100.0, self.soc.value - net_w * dt / 3600 / self.capacity_wh * 100))
        self.soc.set(soc)
        open_v = self.cells * (3.30 + 0.90 * soc / 100)
        amps = net_w / max(open_v, 1.0)
        self.voltage.set(open_v - amps * 0.012 * self.cells + random.gauss(0, 0.004))
        self.current.set(amps)
        t = self.temp.value
        self.temp.set(t + (24.0 + abs(amps) * 0.9 - t) * dt / 20)
        self.remaining.set(soc / 100 * self.capacity_wh / net_w * 60 if net_w > 1 else None)
        lim = self.soc.limits
        if soc <= lim["alarm_low"]:
            st = "CRITICAL"
        elif soc <= lim["warn_low"]:
            st = "LOW"
        else:
            st = "CHARGING" if net_w < -1 else "DISCHARGING" if net_w > 1 else "IDLE"
        self.state.set(st)
