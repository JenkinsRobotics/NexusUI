"""Custom widget for this app. Declares what the widget is; ui.tsx draws it."""
from nexusui.widget import WidgetSpec

SPEC = WidgetSpec(
    type="hello_station_readout", label="Hello Station Readout", category="General",
    description="App-specific widget. Edit ui.tsx to change how it looks.",
    sizes=["s", "m"], bind="channel", accepts=["number"],
)
