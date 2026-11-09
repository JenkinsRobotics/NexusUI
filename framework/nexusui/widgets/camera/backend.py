"""
Camera with a target tracker. The card shows the view, a brightness reading and
a lock flag that goes true when the armed tracker sees its target.

``Set Background`` and ``Set Target Reference`` teach it the two brightness levels;
the lock threshold sits halfway between them. Station logic sets ``target``
(how clearly the target is in view, 0..1).

Real hardware: serve the video as MJPEG and compute ``brightness`` from the
region of interest in ``poll``.
"""
from __future__ import annotations

import random

from nexusui.widget import Device, WidgetSpec, WriteRejected

SPEC = WidgetSpec(
    type="camera", label="Camera", category="Device",
    description="Live camera view with target tracking, arm/disarm and calibration.",
    sizes=["m", "l", "xl"], default_size="l", bind="device",
)


class Camera(Device):
    widget = "camera"

    def __init__(self, engine, id, label=None, *, sim=True):
        super().__init__(engine, id, label, sim=sim)
        self.target = 0.0       # station logic: how clearly the target is in view, 0..1
        self._background = None
        self._reference = None
        self.brightness = self.ch("brightness", min=0, max=1, precision=3, label=f"{self.label} brightness")
        self.exposure = self.ch("exposure", unit="ms", min=1, max=200, step=1, precision=0, writable=True,
                                initial=40, label=f"{self.label} exposure")
        self.fps = self.ch("fps", unit="fps", precision=0, warn_low=5)
        self.armed = self.ch("armed", "bool", writable=True, label=f"{self.label} tracker armed")
        self.locked = self.ch("locked", "bool", label="Target locked")
        self.calibrated = self.ch("calibrated", "bool", label=f"{self.label} calibrated")
        self.cmd("set_background", self._set_background, label="Set Background")
        self.cmd("set_reference", self._set_reference, label="Set Target Reference")
        self.cmd("auto_expose", self._auto, label="Auto-Expose")

    def _set_background(self):
        if self.target > 0.05:
            raise WriteRejected("The background needs the target out of view")
        self._background = self.brightness.value
        self._update_cal()

    def _set_reference(self):
        if self.target < 0.2:
            raise WriteRejected("The reference needs the target in view")
        self._reference = self.brightness.value
        self._update_cal()

    def _auto(self):
        self.exposure.set(60.0)

    def calibrate(self, background: float, reference: float) -> None:
        """Load a known calibration instead of teaching it from the card."""
        self._background, self._reference = background, reference
        self._update_cal()

    def _update_cal(self):
        ok = self._background is not None and self._reference is not None
        self.calibrated.set(ok)
        if ok:
            self.clear("uncal")

    def simulate(self, dt):
        exp = self.exposure.value
        b = min(1.0, 0.04 + self.target * exp / 45 + random.gauss(0, 0.006))
        self.brightness.set(max(0.0, b))
        self.fps.set(min(30.0, 1000.0 / exp))
        if self.calibrated.value:
            threshold = (self._background + self._reference) / 2
        else:
            threshold = 0.3
            if self.armed.value:
                self.alert("uncal", "tracker has no target reference, the lock threshold is a guess")
        self.locked.set(self.armed.value and b > threshold)
