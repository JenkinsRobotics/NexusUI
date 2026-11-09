"""Stat: one value shown large. Small = value only. Medium = value plus trend."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="stat", label="Stat", category="General",
    description="One reading shown large, colored by its alarm limits.",
    sizes=["s", "m"], bind="channel", accepts=["number", "enum", "text", "bool"],
    settings=[setting("trend", "Show trend (medium)", "bool", True)],
)
