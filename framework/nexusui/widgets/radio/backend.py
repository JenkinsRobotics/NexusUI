"""
Telemetry radio link: link on/off behind a permit, transmit power, received
signal, packet loss and a quality figure. The link is refused without a permit
and drops if the permit is lost.

Station logic sets ``permit`` (and ``permit_reason``), ``distance`` in metres and
``interference`` (0..1).
"""
from __future__ import annotations

import math
import random

from nexusui.widget import Device, WidgetSpec

SPEC = WidgetSpec(
    type="radio", label="Radio Link", category="Device",
    description="Radio link card: link on/off with permit, transmit power, signal, packet loss, quality bar.",
    sizes=["s", "m", "t", "l"], default_size="t", bind="device",
)

STATES = {"OFF": "off", "LINKED": "active", "WEAK": "warn", "LOST": "alarm", "NO PERMIT": "warn"}


class Radio(Device):
    widget = "radio"

    def __init__(self, engine, id, label=None, *, max_mw=1000.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.max_mw = max_mw
        self.permit = True
        self.permit_reason = "no permit yet"
        self.distance = 10.0        # metres to the other end, from station logic
        self.interference = 0.0     # 0..1, from station logic
        self.enabled = self.ch("enabled", "bool", writable=True, label=f"{self.label} link")
        self.power = self.ch("power", unit="%", min=1, max=100, step=1, precision=0, writable=True,
                             initial=50.0, label=f"{self.label} transmit power")
        self.tx = self.ch("tx", unit="mW", precision=0, min=0, max=max_mw, label="Transmit")
        self.rssi = self.ch("rssi", unit="dBm", precision=0, label="Signal")
        self.loss = self.ch("loss", unit="%", precision=1, min=0, max=100, warn_high=10, alarm_high=40,
                            label="Packet loss")
        self.quality = self.ch("quality", unit="%", precision=0, min=0, max=100, label="Link quality")
        self.state = self.ch("state", "enum", options=list(STATES), states=STATES)
        self.enabled.interlock(lambda on: f"no link permit ({self.permit_reason})" if on and not self.permit else None)
        self.cmd("link_off", self.link_off, label="Link Off")

    def link_off(self):
        self.enabled.set(False)

    def simulate(self, dt):
        on = self.enabled.value
        if on and not self.permit:
            self.enabled.set(False)
            self.alert("permit", f"link dropped: permit lost ({self.permit_reason})", "alarm")
            on = False
        if not on:
            self.tx.set(0.0)
            self.rssi.set(None)
            self.loss.set(None)
            self.quality.set(0.0)
            self.state.set("OFF" if self.permit else "NO PERMIT")
            return
        tx = self.max_mw * self.power.value / 100
        rssi = (10 * math.log10(tx) - 20 * math.log10(max(self.distance, 1.0)) - 38
                - 25 * self.interference + random.gauss(0, 0.6))
        q = max(0.0, min(100.0, (rssi + 95) * 2.5))      # -95 dBm = 0 %, -55 dBm = 100 %
        self.tx.set(tx)
        self.rssi.set(rssi)
        self.quality.set(q)
        self.loss.set(max(0.0, min(100.0, (60 - q) * 0.9 + random.gauss(0, 0.15))) if q < 60 else 0.0)
        self.state.set("LOST" if q < 8 else "WEAK" if q < 35 else "LINKED")
