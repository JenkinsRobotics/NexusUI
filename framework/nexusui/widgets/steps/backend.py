"""Steps: where a mission or sequence is, shown as a list of its states."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="steps", label="Steps", category="General",
    description="Progress through the states of a mission or sequence, with the current one highlighted.",
    sizes=["t", "m", "l"], default_size="t", min_w=3, min_h=6, bind="channel", accepts=["enum"],
)
