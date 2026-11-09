"""
Motor with a speed controller, for a wheel, a rotor or a propeller: start/stop,
speed and current readback, an eco (reduced speed) mode and a panel lock.
Refuses to start while inhibited and trips if the inhibit appears while running.

Station logic sets ``demand`` (0..1, the speed it wants) and ``inhibit`` (a reason
to refuse running, or None).

Real hardware: replace ``simulate`` with ``poll`` reading the controller, and send
start/stop from ``_write_on``.
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="motor", label="Motor", category="Device",
    description="Motor card for a wheel, rotor or propeller: start/stop, speed, current, eco mode, panel lock.",
    sizes=["s", "m", "t"], default_size="t", bind="device",
)

STATES = {"STOPPED": "off", "SPIN-UP": "info", "RUNNING": "ok", "SPIN-DOWN": "info", "FAULT": "alarm"}


class Motor(Device):
    widget = "motor"

    def __init__(self, engine, id, label=None, *, full_rpm=6000, max_current=12.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.full_rpm = full_rpm
        self.max_current = max_current
        self.demand = 1.0                # station logic: wanted speed, 0..1
        self.inhibit: str | None = None  # station logic: reason the motor may not run
        self.on = self.ch("on", "bool", label=f"{self.label} run", writable=True)
        self.rpm = self.ch("rpm", unit="rpm", precision=0, min=0, max=full_rpm)
        self.current = self.ch("current", unit="A", precision=2, warn_high=max_current * 0.85)
        self.status = self.ch("status", "enum", options=list(STATES), states=STATES)
        self.eco_speed = self.ch("eco_speed", unit="%", min=30, max=100, step=1, precision=0,
                                 writable=True, initial=60, label=f"{self.label} eco speed")
        self.eco_mode = self.ch("eco_mode", "bool", writable=True, label=f"{self.label} eco mode")
        self.locked = self.ch("locked", "bool", writable=True, label=f"{self.label} panel lock")
        self.on.on_write(self._write_on)
        self.on.interlock(lambda start: self._start_block() if start else None)
        self.eco_speed.on_write(self._guard)
        self.eco_mode.on_write(self._guard)

    def _guard(self, v):
        if self.locked.value:
            raise WriteRejected(f"{self.label} panel is locked")
        return v

    def _start_block(self):
        if self.locked.value:
            return "panel is locked"
        return self.inhibit

    def _write_on(self, v):
        if v:
            self.clear("trip")
        return v

    @property
    def at_speed(self) -> bool:
        return self.status.value == "RUNNING"

    def simulate(self, dt):
        target = 0.0
        if self.on.value:
            if self.inhibit:
                self.on.set(False)
                self.status.set("FAULT")
                self.alert("trip", f"stopped: {self.inhibit}", "alarm")
                return
            limit = self.eco_speed.value / 100 if self.eco_mode.value else 1.0
            target = self.full_rpm * max(0.0, min(1.0, self.demand)) * limit
        rpm = self.rpm.value or 0.0
        rate = self.full_rpm * (1.2 if target > rpm else 0.8)          # rpm per second
        step = max(-rate * dt, min(rate * dt, target - rpm))
        rpm += step
        self.rpm.set(rpm)
        load = rpm / self.full_rpm
        spinning = rpm > self.full_rpm * 0.01
        self.current.set((0.3 + self.max_current * 0.6 * load ** 2 + (self.max_current * 0.2 if step > 1e-6 else 0)
                          + random.gauss(0, 0.02)) if spinning else 0.0)
        if not spinning and target == 0:
            st = "FAULT" if self.status.value == "FAULT" else "STOPPED"
        elif abs(target - rpm) < self.full_rpm * 0.02:
            st = "RUNNING" if target > 0 else "STOPPED"
        else:
            st = "SPIN-UP" if target > rpm else "SPIN-DOWN"
        self.status.set(st)
