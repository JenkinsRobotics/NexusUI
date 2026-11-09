"""
Widget Gallery
==============
Every widget in the framework on one station, driven by simulated hardware.

  Basics   a bench power supply heating a board: readouts, gauges, switches, sliders,
           buttons, a trend, a panel, the event log and a note
  Devices  the ten premade device cards
  Motion   the widgets for things that move: track map, attitude, range scan,
           bar gauge, mission steps and a joystick, driven by a small cart
  Diagram  a live system diagram

Try it: on Basics, switch the output on, raise the setpoint to 24 V and set the fan
to LOW. The board warms up, warns, alarms and trips; the output then stays locked
until it cools and you press Reset Trip.

Run:  python apps/widget_gallery/app.py             opens in its own window
      python apps/widget_gallery/app.py --browser   then open http://localhost:8000, from any device
"""
import argparse
import json
import math
import random
import time

from nexusui import Diagram, Engine, WriteRejected
from nexusui.widgets.battery.backend import Battery
from nexusui.widgets.beacon.backend import Beacon
from nexusui.widgets.camera.backend import Camera
from nexusui.widgets.heater.backend import Heater
from nexusui.widgets.motor.backend import Motor
from nexusui.widgets.power_meter.backend import PowerMeter
from nexusui.widgets.pump.backend import Pump
from nexusui.widgets.radio.backend import Radio
from nexusui.widgets.range_sensor.backend import RangeSensor
from nexusui.widgets.servo.backend import Servo

# "open": anyone can operate, so every control responds on the first click.
# Real rigs use the default control="lock" (one station operates, the others view).
eng = Engine("Widget Gallery", control="open")

# ---------------------------------------------------------------- Basics: bench supply
LOAD_OHMS = 8.0
TRIP_C, RESET_C = 85.0, 50.0

output = eng.channel("psu.output", "bool", label="Output", writable=True)
vset = eng.channel("psu.vset", label="Voltage Setpoint", unit="V", min=0, max=24, step=0.1,
                   precision=1, writable=True, initial=12)
voltage = eng.channel("psu.voltage", label="Voltage", unit="V", min=0, max=24, precision=2)
current = eng.channel("psu.current", label="Current", unit="A", min=0, max=4, precision=2,
                      warn_high=2.5, alarm_high=3.2)
power = eng.channel("psu.power", label="Power", unit="W", min=0, max=80, precision=1)
temp = eng.channel("board.temp", label="Board Temperature", unit="°C", min=0, max=100, precision=1,
                   warn_high=65, alarm_high=80, initial=25)
fan = eng.channel("board.fan", "enum", label="Fan", options=["AUTO", "LOW", "HIGH"], writable=True)
state = eng.channel("board.state", "enum", label="State", options=["IDLE", "RUNNING", "FAULT"],
                    states={"IDLE": "off", "RUNNING": "ok", "FAULT": "alarm"})
tripped = eng.channel("board.tripped", "bool", label="Over-temperature Trip")


@output.interlock
def _(on):
    if on and tripped.value:
        return "over-temperature trip; let the board cool, then press Reset Trip"


@eng.command("psu.reset_trip", label="Reset Trip")
def reset_trip():
    if temp.value > RESET_C:
        raise WriteRejected(f"Board is still above {RESET_C:g} °C")
    tripped.set(False)
    eng.clear_alert("psu:trip")


@eng.command("psu.all_off", label="All Off", danger=True)
def all_off():
    output.set(False)
    motor.on.set(False)
    radio.enabled.set(False)
    beacon.output.set(False)


# ---------------------------------------------------------------- Devices
motor = Motor(eng, "motor1", "Drive Motor")
servo = Servo(eng, "servo1", "Steering Servo")
pump = Pump(eng, "pump1", "Coolant Pump")
heater = Heater(eng, "heater1", "Sensor Heater")
ranger = RangeSensor(eng, "range1", "Lidar", max_range=40, warn_below=3)
beacon = Beacon(eng, "beacon1", "Beacon")
radio = Radio(eng, "radio1", "Radio Link")
battery = Battery(eng, "battery1", "Battery", capacity_wh=30)
pm = PowerMeter(eng, "pm", "Power Meter")
cam = Camera(eng, "cam", "Camera")
devices = (motor, servo, pump, heater, ranger, radio, battery, pm, cam)

# A real station works these out from its own logic; the gallery pins them to easy values.
radio.distance = 600        # metres to the other end of the link

# ---------------------------------------------------------------- Motion: a small cart
CART_ROUTE = [(round(20 * math.sin(a), 2), round(12 * math.sin(2 * a), 2)) for a in (k * math.pi / 12 for k in range(25))]

cart_x = eng.channel("cart.x", label="Cart east", unit="m", precision=1)
cart_y = eng.channel("cart.y", label="Cart north", unit="m", precision=1)
cart_heading = eng.channel("cart.heading", label="Heading", unit="°", precision=0)
cart_roll = eng.channel("cart.roll", label="Roll", unit="°", precision=1)
cart_pitch = eng.channel("cart.pitch", label="Pitch", unit="°", precision=1)
cart_route = eng.channel("cart.route", "text", label="Route", initial=json.dumps(CART_ROUTE))
cart_scan = eng.channel("cart.scan", "text", label="Scan", urgent=False)
cart_leg = eng.channel("cart.leg", "enum", label="Lap", options=["EAST LOOP", "CROSSING", "WEST LOOP", "RETURN"],
                       states={"EAST LOOP": "ok", "CROSSING": "info", "WEST LOOP": "ok", "RETURN": "info"})
lift = eng.channel("cart.lift", label="Mast Height", unit="m", min=0, max=8, precision=2)
lift_set = eng.channel("cart.lift_set", label="Mast Target", unit="m", min=0, max=8, step=0.1, precision=1,
                       writable=True, initial=5)
joy_x = eng.channel("cart.joy_x", label="Nudge east", min=-1, max=1, precision=2, writable=True, quiet=True)
joy_y = eng.channel("cart.joy_y", label="Nudge north", min=-1, max=1, precision=2, writable=True, quiet=True)

t0 = time.monotonic()
ticks = {"n": 0}

# ---------------------------------------------------------------- Diagram
d = Diagram(eng, "power", "Power Path", width=760, height=260)
d.equipment("psu", 40, 90, 150, 80, "Supply", on="psu.output", values=["psu.voltage"])
d.pipe((190, 130), (430, 130), when=["psu.output"], kind="power")
d.valve("relay", 310, 130, "psu.output", "Output", label_pos="below")
d.vessel("load", 430, 60, 230, 140, "Load", value="psu.current", state="board.state")
d.gauge("tc", 710, 130, "board.temp", "TC")


@eng.on_start
def power_up():
    """Start with the device cards showing something."""
    motor.on.set(True)
    ranger.emit.set(True)
    radio.enabled.set(True)
    beacon.output.set(True)
    servo.command_pct.set(55.0)
    pump.setpoint.set(8.0)


@eng.loop(hz=50)
def physics(dt):
    # supply: voltage follows the setpoint, the load draws current and heats the board
    target = vset.value if output.value else 0.0
    v = voltage.value + (target - voltage.value) * min(1.0, dt / 0.15)
    i = v / LOAD_OHMS * (1 + random.gauss(0, 0.004)) if v > 0.01 else 0.0
    voltage.set(v)
    current.set(i)
    power.set(v * i)

    t = temp.value
    airflow = {"LOW": 0.3, "HIGH": 1.0}.get(fan.value, min(1.0, max(0.2, (t - 40) / 20)))
    t += (v * i * 0.9 - (t - 25) * (0.4 + 1.6 * airflow)) * dt / 6
    temp.set(t)
    if t >= TRIP_C and not tripped.value:
        tripped.set(True)
        output.set(False)
        eng.alert("psu:trip", "Over-temperature trip: output switched off", "alarm", source="psu")
    state.set("FAULT" if tripped.value else "RUNNING" if output.value else "IDLE")

    # devices: the battery feeds the motor, the meter reads that load, the camera sees the beacon
    now = time.monotonic() - t0
    load_w = 6 + 55 * motor.rpm.value / motor.full_rpm
    battery.load_w = pm.true_w = load_w
    pm.true_v = battery.voltage.value or 0.0
    ranger.true_range = 14 + 9 * math.sin(now / 6)
    cam.target = beacon.strength
    for dev in devices:
        dev.step(dt)

    # motion: the cart laps a figure of eight over bumpy ground; the stick nudges it off the line
    a = now / 9
    cart_x.set(20 * math.sin(a) + 4 * joy_x.value)
    cart_y.set(12 * math.sin(2 * a) + 4 * joy_y.value)
    cart_heading.set(math.degrees(math.atan2(20 * math.cos(a), 24 * math.cos(2 * a))) % 360)
    cart_roll.set(11 * math.sin(now / 2.1) + 3 * math.sin(now / 0.7))
    cart_pitch.set(7 * math.sin(now / 3.3))
    cart_leg.set(cart_leg.options[int((a % (2 * math.pi)) / (math.pi / 2))])
    lift.set(lift.value + max(-1.2 * dt, min(1.2 * dt, lift_set.value - lift.value)))
    ticks["n"] += 1
    if ticks["n"] % 5 == 0:     # the scan updates ten times a second
        cart_scan.set(json.dumps([round(9 + 5 * math.sin(k / 3 + now / 2) + 2 * math.sin(k * 1.7), 1) for k in range(37)]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true", help="serve browsers on the network instead of opening a window")
    ap.add_argument("--port", type=int)
    a = ap.parse_args()
    eng.run(port=a.port, desktop=False if a.browser else None)
