"""Indicator: status lamp for a boolean or state channel."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="indicator", label="Indicator", category="General",
    description="Lamp for a status bit or a state like OK / LOCKED / TRIPPED.",
    sizes=["s", "m"], bind="channel", accepts=["bool", "enum"],
    settings=[setting("on_text", "On text", "text", "ON"), setting("off_text", "Off text", "text", "OFF")],
)
