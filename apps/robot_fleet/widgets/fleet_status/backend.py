"""Fleet status strip: one cell per robot and a stop-everything button. Specific to this app."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="fleet_status", label="Fleet Status", category="General",
    description="Status strip for the robot fleet: each robot's state and key readings, and Stop All.",
    sizes=["xl"], default_size="xl", min_w=12, min_h=6,
)
