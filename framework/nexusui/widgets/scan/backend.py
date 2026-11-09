"""Range scan: a lidar or sonar sweep seen from above."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="scan", label="Range Scan", category="General",
    description="Polar view of a lidar or sonar sweep. Bind a text channel holding a JSON list of ranges, "
                "spread evenly across the field of view.",
    sizes=["l", "s", "xl"], default_size="l", min_w=4, min_h=10, bind="channel", accepts=["text"],
    settings=[
        setting("max_range", "Max range", "number", 20),
        setting("fov", "Field of view (degrees)", "number", 180),
        setting("unit", "Unit", "text", "m"),
    ],
)
