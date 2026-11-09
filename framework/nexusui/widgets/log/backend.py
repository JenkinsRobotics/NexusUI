"""Event log: the engine's activity feed (writes, commands, alerts, stations)."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="log", label="Event Log", category="General",
    description="Live feed of who did what, alerts and engine events.",
    sizes=["m", "l", "xl"], default_size="l",
    settings=[setting("level", "Show", "select", "all", options=["all", "warn", "alarm"])],
)
