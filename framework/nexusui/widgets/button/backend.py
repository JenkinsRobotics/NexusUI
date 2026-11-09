"""Button: run a command. Dangerous commands need press-and-hold."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="button", label="Command Button", category="Control",
    description="Runs an engine command. Commands marked danger need a 0.8 s hold.",
    sizes=["s", "m"], bind="command",
)
