"""Attitude: an artificial horizon for anything that rolls and pitches."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="attitude", label="Attitude", category="General",
    description="Artificial horizon with a heading readout. Bind roll, pitch and heading, in that order, in degrees.",
    sizes=["l", "s", "xl"], default_size="l", min_w=4, min_h=10, bind="channels", accepts=["number"],
)
