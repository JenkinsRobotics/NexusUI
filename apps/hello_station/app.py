"""
Hello Station
=============
Backend for this app. The screen layout lives in layouts/*.json and is
edited from the UI (Edit layout). Custom widgets go in widgets/<type>/.

Run:  python apps/hello_station/app.py             opens in its own window
      python apps/hello_station/app.py --browser   then open http://localhost:8000, from any device
"""
import argparse

from nexusui import Engine
from nexusui.widgets.motor.backend import Motor   # premade device from the framework

eng = Engine("Hello Station", control="lock")

temp = eng.channel("demo.temp", label="Temperature", unit="°C", precision=1, warn_high=80, alarm_high=95)
heater = eng.channel("demo.heater", "bool", label="Heater", writable=True)
setpoint = eng.channel("demo.setpoint", label="Setpoint", unit="°C", min=20, max=90, writable=True, initial=50)
fan = Motor(eng, "fan1", "Fan", full_rpm=3000)


@eng.command("demo.all_off", label="All Off", danger=True)
def all_off():
    heater.set(False)
    fan.on.set(False)


@eng.on_control_lost
def safe():
    all_off()


@eng.loop(hz=50)
def physics(dt):
    t = temp.value
    target = setpoint.value if heater.value else 22.0
    temp.set(t + (target - t) * dt / 8)
    fan.step(dt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true", help="serve browsers on the network instead of opening a window")
    ap.add_argument("--port", type=int)
    a = ap.parse_args()
    eng.run(port=a.port, desktop=False if a.browser else None)
