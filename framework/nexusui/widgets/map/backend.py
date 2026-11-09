"""Track map: where the vehicles are and where they have been, seen from above."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="map", label="Track Map", category="General",
    description="Top-down map of one or more vehicles with their trails. Bind channels in groups of three: "
                "x, y and heading for each vehicle. Waypoints come from a text channel holding a JSON list of [x, y].",
    sizes=["l", "xl"], default_size="xl", min_w=6, min_h=12, bind="channels", accepts=["number"],
    settings=[
        setting("extent", "Half-width shown (0 = fit)", "number", 0),
        setting("trail", "Trail length (s)", "number", 120),
        setting("waypoints", "Waypoints channel", "channel"),
        setting("unit", "Unit", "text", "m"),
    ],
)
