"""Joystick: a two-axis stick for manual driving."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="joystick", label="Joystick", category="Control",
    description="Two-axis stick. Bind two writable numbers: left/right, then forward/back. Springs back to centre.",
    sizes=["s", "l"], default_size="s", min_w=3, min_h=8, bind="channels", accepts=["number"], writable_only=True,
)
