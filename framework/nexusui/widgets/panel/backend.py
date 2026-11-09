"""Panel: a titled list of channels and commands. Each row renders by data type:
readings show values, outputs get ON/OFF buttons, setpoints get input boxes,
states get colored chips."""
from nexusui.widget import WidgetSpec, setting

SPEC = WidgetSpec(
    type="panel", label="Panel", category="General",
    description="List of any channels and commands, like an instrument front panel.",
    sizes=["m", "l", "t"], default_size="t",
    bind="channels", accepts=["number", "bool", "enum", "text"],
    settings=[
        setting("commands", "Command buttons", "commands", []),
        setting("compact", "Compact rows", "bool", False),
    ],
)
