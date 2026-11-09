"""NexusUI: Python engines for real-time hardware, with one UI for browser and desktop."""
from .engine import Channel, Engine, WriteRejected
from .diagram import Diagram
from .widget import SIZES, Device, WidgetSpec, discover_widgets, setting

__version__ = "1.0.0"
__all__ = ["Engine", "Diagram", "Channel", "Device", "WidgetSpec", "WriteRejected", "SIZES", "setting",
           "discover_widgets"]
