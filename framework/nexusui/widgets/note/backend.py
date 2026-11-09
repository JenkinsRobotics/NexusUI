"""Note: static operator guidance text."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="note", label="Note", category="General",
    description="Operator guidance, procedures or limits written into the layout.",
    sizes=["s", "m", "l", "t"], default_size="m", min_h=3,
    settings=[setting("text", "Text", "textarea", "")],
)
