"""
Metering pump or flow meter, for ballast, sampling or coolant: flow, pressure,
temperature, running total, fluid select, zero and reset. Pumps add a setpoint
and a control mode; meters are read-only.
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="pump", label="Pump", category="Device",
    description="Metering pump or flow meter card: setpoint, flow, pressure, total, fluid select, zero.",
    sizes=["s", "m", "t", "l"], default_size="t", bind="device",
)


class Pump(Device):
    widget = "pump"

    def __init__(self, engine, id, label=None, *, full_scale=20.0, controller=True,
                 fluid="Water", fluids=("Water", "Seawater", "Coolant"), sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.full_scale = full_scale
        self.controller = controller
        self.sim_flow = 0.0              # meters: station logic sets the true flow
        self.sim_pressure = 101.3
        self._true = 0.0
        self._offset = random.uniform(-0.02, 0.02) * full_scale
        self.flow = self.ch("flow", unit="L/min", precision=2, min=0, max=full_scale)
        self.pressure = self.ch("pressure", unit="kPa", precision=1)
        self.temp = self.ch("temp", unit="°C", precision=1, initial=18.0)
        self.total = self.ch("total", unit="L", precision=2)
        self.fluid = self.ch("fluid", "enum", options=list(fluids), initial=fluid, writable=True)
        if controller:
            self.setpoint = self.ch("setpoint", unit="L/min", min=0, max=full_scale, step=0.1,
                                    precision=1, writable=True)
            self.mode = self.ch("mode", "enum", options=["Normal", "Hold", "Stopped"], writable=True,
                                states={"Normal": "ok", "Hold": "warn", "Stopped": "off"})
        self.cmd("zero", self._zero, label="Zero", description="Zero the reading. Flow must be stopped.")
        self.cmd("reset_total", self._reset_total, label="Reset Total")

    @property
    def true_flow(self) -> float:
        return self._true if self.controller else self.sim_flow

    def _zero(self):
        if abs(self.true_flow) > self.full_scale * 0.01:
            raise WriteRejected(f"{self.label}: stop the flow before zeroing")
        self._offset = 0.0

    def _reset_total(self):
        self.total.set(0.0)

    def simulate(self, dt):
        if self.controller:
            target = 0.0 if self.mode.value == "Stopped" else self.setpoint.value
            if self.mode.value != "Hold":
                self._true += (target - self._true) * min(1.0, dt / 0.25)
        flow = self.true_flow + self._offset + random.gauss(0, self.full_scale * 0.0004)
        self.flow.set(flow)
        self.total.set((self.total.value or 0.0) + max(0.0, self.true_flow) * dt / 60)
        self.pressure.set(self.sim_pressure + self.true_flow * 1.5 + random.gauss(0, 0.05))
        self.temp.set(18.0 + random.gauss(0, 0.03))
