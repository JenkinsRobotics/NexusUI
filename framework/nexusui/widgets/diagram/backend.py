"""
Diagram: draws a live system diagram defined by the app with nexusui.Diagram.
The framework owns the drawing; each app owns its diagrams.
"""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="diagram", label="Diagram", category="General",
    description="Live system diagram from the app: units, switches, readouts and animated links.",
    sizes=["m", "l", "xl"], default_size="xl", min_w=6, min_h=10,
    settings=[setting("diagram", "Diagram", "diagram")],
)
