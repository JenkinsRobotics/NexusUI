"""Chart: live trend of one or more channels, GPU-friendly canvas rendering."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="chart", label="Trend Chart", category="Trend",
    description="Scrolling trend of several channels. Supports a log scale.",
    sizes=["m", "l", "xl"], default_size="l",
    bind="channels", accepts=["number"],
    settings=[
        setting("window", "Time window (s)", "number", 60, min=5, max=120),
        setting("log", "Log scale", "bool", False),
    ],
)
