"""
nexusui.desktop
----------------
Native desktop window for a station, using the system web engine
(Edge WebView2 on Windows, WebKit on macOS/Linux) through pywebview.

The window shows exactly the same UI a browser would, so a laptop can run the
engine locally and offline, or open a station on another machine:

    python -m nexusui.desktop http://192.168.1.20:8000
"""
from __future__ import annotations

import argparse
import sys


def open_window(url: str, title: str = "NexusUI Station", *, width: int = 1600, height: int = 950,
                fullscreen: bool = False) -> None:
    try:
        import webview
    except ImportError:
        sys.exit("A standalone window needs pywebview:  pip install pywebview")
    webview.create_window(title, url, width=width, height=height, min_size=(900, 600),
                          fullscreen=fullscreen, background_color="#0b0e13", text_select=False)
    webview.start()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Open a NexusUI station in a desktop window.")
    p.add_argument("url", nargs="?", default="http://localhost:8000", help="engine address")
    p.add_argument("--title", default="NexusUI Station")
    p.add_argument("--fullscreen", action="store_true")
    a = p.parse_args(argv)
    open_window(a.url, a.title, fullscreen=a.fullscreen)


if __name__ == "__main__":
    main()
