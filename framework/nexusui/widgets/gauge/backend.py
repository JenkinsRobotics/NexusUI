"""Gauge: arc gauge with warning and alarm bands."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="gauge", label="Gauge", category="General",
    description="Arc gauge with limit bands. Large adds ticks and a trend.",
    sizes=["s", "m", "l"], default_size="s", bind="channel", accepts=["number"],
    settings=[setting("min", "Scale min", "number"), setting("max", "Scale max", "number")],
)
