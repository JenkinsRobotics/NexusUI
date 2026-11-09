"""
Toolkit comparison: the bench supply panel in NexusUI
======================================================
The same panel is written five ways in this folder: app.py (this file), tk_app.py
(Tkinter), qt_app.py (PyQt6), rust_app/ (all Rust, a native egui screen) and rust_engine/
(a Rust engine under this same React UI). run.py launches them and measures each.

Run:  python apps/toolkit_comparison/app.py             opens in its own window
      python apps/toolkit_comparison/app.py --browser   then open http://localhost:8000, from any device
"""
import argparse
import random

from nexusui import Engine, WriteRejected

LOAD_OHMS, TRIP_C, RESET_C = 8.0, 85.0, 50.0
eng = Engine("Bench Supply", control="open")

output = eng.channel("psu.output", "bool", label="Output", writable=True)
vset = eng.channel("psu.vset", label="Setpoint", unit="V", min=0, max=24, step=0.1, precision=1, writable=True, initial=12)
voltage = eng.channel("psu.voltage", label="Voltage", unit="V", min=0, max=24, precision=2)
current = eng.channel("psu.current", label="Current", unit="A", min=0, max=4, precision=2)
temp = eng.channel("board.temp", label="Temperature", unit="°C", min=0, max=100, precision=1,
                   warn_high=65, alarm_high=80, initial=25)
fan = eng.channel("board.fan", "enum", label="Fan", options=["AUTO", "LOW", "HIGH"], writable=True)
state = eng.channel("board.state", "enum", label="State", options=["IDLE", "RUNNING", "FAULT"],
                    states={"IDLE": "off", "RUNNING": "ok", "FAULT": "alarm"})
tripped = eng.channel("board.tripped", "bool", label="Tripped")


@output.interlock
def _(on):
    if on and tripped.value:
        return "over-temperature trip; let the board cool, then press Reset Trip"


@eng.command("psu.reset_trip", label="Reset Trip")
def reset_trip():
    if temp.value > RESET_C:
        raise WriteRejected(f"Board is still above {RESET_C:g} °C")
    tripped.set(False)


@eng.loop(hz=50)
def physics(dt):
    target = vset.value if output.value else 0.0
    v = voltage.value + (target - voltage.value) * min(1.0, dt / 0.15)
    i = v / LOAD_OHMS * (1 + random.gauss(0, 0.004)) if v > 0.01 else 0.0
    t = temp.value
    airflow = {"LOW": 0.3, "HIGH": 1.0}.get(fan.value, min(1.0, max(0.2, (t - 40) / 20)))
    t += (v * i * 0.9 - (t - 25) * (0.4 + 1.6 * airflow)) * dt / 6
    voltage.set(v)
    current.set(i)
    temp.set(t)
    if t >= TRIP_C and not tripped.value:
        tripped.set(True)
        output.set(False)
    state.set("FAULT" if tripped.value else "RUNNING" if output.value else "IDLE")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true", help="serve browsers on the network instead of opening a window")
    ap.add_argument("--port", type=int)
    a = ap.parse_args()
    eng.run(port=a.port, desktop=False if a.browser else None)
