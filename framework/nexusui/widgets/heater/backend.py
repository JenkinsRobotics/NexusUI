"""
Heated element with a warm-up, for a battery, a sensor window or a payload bay:
heater on/off, temperature and a ready state. The heater is refused while
inhibited and switches off if the inhibit appears once it is hot.

Station logic sets ``ambient`` (the temperature it settles to when off) and
``inhibit`` (a reason the heater may not run, or None).
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec

SPEC = WidgetSpec(
    type="heater", label="Heater", category="Device",
    description="Heater card: on/off, temperature, warm-up, ready state and inhibit fault.",
    sizes=["s", "m", "t"], default_size="s", bind="device",
)

STATES = {"COLD": "off", "WARMING": "info", "READY": "ok", "COOLING": "info", "FAULT": "alarm"}


class Heater(Device):
    widget = "heater"

    def __init__(self, engine, id, label=None, *, target_c=40.0, ready_c=30.0, max_c=70.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.target_c = target_c
        self.ready_c = ready_c
        self.ambient = 20.0              # station logic sets the surrounding temperature
        self.inhibit: str | None = None  # station logic: reason the heater may not run
        self.heater = self.ch("heater", "bool", writable=True, label=f"{self.label} heater")
        self.temp = self.ch("temp", unit="°C", precision=1, initial=20.0, min=-20, max=max_c,
                            warn_high=max_c * 0.85)
        self.state = self.ch("state", "enum", options=list(STATES), states=STATES)
        self.heater.on_write(self._write_heater)
        self.heater.interlock(lambda on: self.inhibit if on else None)

    def _write_heater(self, v):
        if v:
            self.clear("inhibit")
        return v

    @property
    def ready(self) -> bool:
        return self.state.value == "READY"

    def simulate(self, dt):
        t = self.temp.value
        if self.heater.value and self.inhibit:
            self.heater.set(False)
            self.state.set("FAULT")
            self.alert("inhibit", f"heater off at {t:.0f} °C: {self.inhibit}", "alarm")
        target = self.target_c if self.heater.value else self.ambient
        t += (target - t) * dt / (12.0 if self.heater.value else 30.0)
        self.temp.set(t + random.gauss(0, 0.02))
        if self.state.value == "FAULT" and not self.heater.value and t > self.ambient + 3:
            return
        if self.heater.value:
            self.state.set("READY" if t >= self.ready_c else "WARMING")
        else:
            self.state.set("COLD" if t < self.ambient + 3 else "COOLING")
