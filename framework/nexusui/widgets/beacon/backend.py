"""
Signal beacon, for an acoustic pinger, a strobe or a radio tone: output on/off,
frequency, level, pattern and timing. No simulator is needed: it only holds settings.
"""
from __future__ import annotations

from nexusui.widget import Device, WidgetSpec

SPEC = WidgetSpec(
    type="beacon", label="Beacon", category="Device",
    description="Beacon card: output, frequency, level, pattern and timing.",
    sizes=["s", "m", "t"], default_size="t", bind="device",
)


class Beacon(Device):
    widget = "beacon"

    def __init__(self, engine, id, label=None, *, freq_khz=25.0, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.output = self.ch("output", "bool", writable=True, label=f"{self.label} output")
        self.freq = self.ch("freq", unit="kHz", min=1, max=100, step=0.1, precision=1,
                            writable=True, initial=freq_khz, label=f"{self.label} frequency")
        self.level = self.ch("level", unit="%", min=0, max=100, step=1, precision=0,
                             writable=True, initial=60, label=f"{self.label} level")
        self.pattern = self.ch("pattern", "enum", options=["steady", "pulse", "double", "sweep"],
                               writable=True, initial="pulse", label=f"{self.label} pattern")
        self.interval = self.ch("interval", unit="s", min=0.1, max=10, step=0.1, precision=1,
                                writable=True, initial=1.0, label=f"{self.label} interval")
        self.delay = self.ch("delay", unit="ms", min=0, max=500, step=1, precision=0,
                             writable=True, label=f"{self.label} delay")

    @property
    def strength(self) -> float:
        """Output strength, 0..1 (0 while the output is off)."""
        return self.level.value / 100 if self.output.value else 0.0
