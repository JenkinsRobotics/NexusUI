"""Bar gauge: a tall or wide bar with a scale, limit colours and an optional target marker."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="bar", label="Bar Gauge", category="General",
    description="Bar with a scale, limit colours and a target marker. Can read downward, for depth.",
    sizes=["t", "s", "m"], default_size="t", min_w=2, min_h=8, bind="channel", accepts=["number"],
    settings=[
        setting("min", "Scale min", "number"), setting("max", "Scale max", "number"),
        setting("target", "Target channel", "channel"),
        setting("invert", "Zero at the top (depth)", "bool", False),
        setting("horizontal", "Horizontal", "bool", False),
    ],
)
