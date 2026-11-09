"""Slider: setpoint control with readback."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="slider", label="Setpoint", category="Control",
    description="Drag or type a setpoint. Large adds fine steps and the readback.",
    sizes=["m", "l"], bind="channel", accepts=["number"], writable_only=True,
    settings=[setting("readback", "Readback channel", "channel")],
)
