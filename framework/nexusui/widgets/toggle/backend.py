"""Toggle: operate a boolean output such as a valve, pump or enable."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="toggle", label="Toggle", category="Control",
    description="Switch for an on/off output. Shows who last changed it.",
    sizes=["s", "m"], bind="channel", accepts=["bool"], writable_only=True,
    settings=[setting("on_text", "On text", "text", "ON"), setting("off_text", "Off text", "text", "OFF")],
)
