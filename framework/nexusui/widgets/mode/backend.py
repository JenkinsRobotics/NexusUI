"""Mode: segmented selector for a state such as SAFE / ARMED / FIRING."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="mode", label="Mode Selector", category="Control",
    description="Segmented selector for a writable state channel.",
    sizes=["m", "xl"], bind="channel", accepts=["enum"], writable_only=True,
)
