"""
Robot Fleet
===========
Three simulated robots on one station, each with its own workspace:

  Survey Rover   a ground rover driving a survey grid: track map, lidar scan,
                 mission steps, a manual stick, drive motors and battery
  Drone          a quadcopter flying a pattern: attitude, altitude, four rotors,
                 gimbal camera with a target tracker, telemetry radio
  Sub + Boat     an underwater vehicle on a tether and the surface tender that
                 follows it: depth, forward sonar, ballast, winch, shared map

Everything here is simulated; the robots start their missions by themselves so the
screens are alive from the first second. Take control to drive them yourself.

Run:   python apps/robot_fleet/app.py             (opens in its own window)
       python apps/robot_fleet/app.py --browser   (browser: http://localhost:8000, from any device)
"""
from __future__ import annotations

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

eng = Engine("Robot Fleet", control="lock")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def approach(v, target, step):
    return v + clamp(target - v, -step, step)


def wrap180(a):
    return (a + 180) % 360 - 180


def bearing(dx, dy):
    """Heading in degrees, clockwise from north (+y), toward (dx, dy)."""
    return math.degrees(math.atan2(dx, dy)) % 360


def step_toward(pos, heading, target, speed, turn_rate, dt):
    """Turn toward the target and move forward. Returns (x, y, heading, turn in deg/s)."""
    err = wrap180(bearing(target[0] - pos[0], target[1] - pos[1]) - heading)
    turn = clamp(err * 2.5, -turn_rate, turn_rate)
    heading = (heading + turn * dt) % 360
    rad = math.radians(heading)
    return pos[0] + math.sin(rad) * speed * dt, pos[1] + math.cos(rad) * speed * dt, heading, turn


# ============================================================== SURVEY ROVER
ROVER_DOCK = (-30.0, -20.0)
ROVER_ROUTE = [(x, y) for n, y in enumerate(range(-15, 16, 6)) for x in ((-24.0, 24.0) if n % 2 == 0 else (24.0, -24.0))]
ROCKS = [(-10.0, -12.0, 1.3), (12.0, -6.0, 1.6), (-2.0, 0.0, 1.1), (16.0, 6.0, 1.4), (-17.0, 12.0, 1.2)]   # x, y, radius
FENCE = (34.0, 24.0)   # half-width and half-height of the fenced field
ROVER_VMAX = 2.5

r_x = eng.channel("rover.x", label="Rover east", unit="m", precision=1, initial=ROVER_DOCK[0])
r_y = eng.channel("rover.y", label="Rover north", unit="m", precision=1, initial=ROVER_DOCK[1])
r_heading = eng.channel("rover.heading", label="Heading", unit="°", precision=0, initial=45)
r_speed = eng.channel("rover.speed", label="Speed", unit="m/s", precision=2, min=0, max=ROVER_VMAX)
r_cruise = eng.channel("rover.cruise", label="Cruise Speed", unit="m/s", min=0.3, max=ROVER_VMAX, step=0.1,
                       precision=1, writable=True, initial=1.6)
r_mode = eng.channel("rover.mode", "enum", label="Drive Mode", options=["AUTO", "MANUAL", "HOLD"], writable=True)
r_mission = eng.channel("rover.mission", "enum", label="Mission", options=["DOCKED", "TRANSIT", "SURVEY", "RETURN"],
                        states={"DOCKED": "off", "TRANSIT": "info", "SURVEY": "ok", "RETURN": "info"}, initial="TRANSIT")
r_coverage = eng.channel("rover.coverage", label="Field Covered", unit="%", precision=0, min=0, max=100)
r_odometer = eng.channel("rover.odometer", label="Distance Driven", unit="m", precision=0)
r_reading = eng.channel("rover.reading", label="Ground Reading", unit="nT", precision=1, min=0, max=120)
r_clearance = eng.channel("rover.clearance", label="Nearest Obstacle", unit="m", precision=1, min=0, max=20,
                          warn_low=2.5, alarm_low=1.2, initial=20)
r_estop = eng.channel("rover.estop", "bool", label="Rover E-Stop")
r_scan = eng.channel("rover.scan", "text", label="Lidar Scan", urgent=False)
r_waypoints = eng.channel("rover.waypoints", "text", label="Survey Route", initial=json.dumps([ROVER_DOCK, *ROVER_ROUTE]))
r_joy_x = eng.channel("rover.joy_x", label="Steer", min=-1, max=1, precision=2, writable=True, quiet=True)
r_joy_y = eng.channel("rover.joy_y", label="Throttle", min=-1, max=1, precision=2, writable=True, quiet=True)

r_left = Motor(eng, "rover_left", "Left Drive", full_rpm=3000, max_current=18)
r_right = Motor(eng, "rover_right", "Right Drive", full_rpm=3000, max_current=18)
r_batt = Battery(eng, "rover_batt", "Rover Battery", capacity_wh=5, cells=6)   # small, so a survey visibly drains it
r_lidar = RangeSensor(eng, "rover_lidar", "Lidar", max_range=20, warn_below=2.5)

rover = {"wp": 0, "v": 0.0, "joy_at": 0.0, "docked_for": 0.0}


def _stick(v):
    rover["joy_at"] = time.monotonic()
    return v


r_joy_x.on_write(_stick)
r_joy_y.on_write(_stick)


@r_mode.interlock
def _(mode):
    if mode != "HOLD" and r_estop.value:
        return "E-stop is pressed; reset it first"


@eng.command("rover.start", label="Start Survey")
def rover_start():
    if r_estop.value:
        raise WriteRejected("Reset the E-stop first")
    if r_batt.critical:
        raise WriteRejected("Rover battery is critical; let it charge")
    rover["wp"] = 0
    r_mission.set("TRANSIT")
    r_mode.set("AUTO")
    for m in (r_left, r_right):
        m.on.set(True)


@eng.command("rover.dock", label="Return to Dock")
def rover_dock():
    if r_mission.value != "DOCKED":
        r_mission.set("RETURN")
        r_mode.set("AUTO")


@eng.command("rover.estop", label="E-Stop", danger=True)
def rover_estop():
    r_estop.set(True)
    r_mode.set("HOLD")
    eng.alert("rover:estop", "Rover E-stop pressed: drives stopped", "alarm", source="rover")


@eng.command("rover.reset", label="Reset E-Stop")
def rover_reset():
    r_estop.set(False)
    eng.clear_alert("rover:estop")
    for m in (r_left, r_right):
        m.on.set(True)


def lidar_scan(x, y, heading, beams=37, fov=180.0, max_range=20.0):
    """Ranges across the field of view, left to right, to the rocks and the fence."""
    out = []
    for k in range(beams):
        a = math.radians(heading - fov / 2 + fov * k / (beams - 1))
        dx, dy = math.sin(a), math.cos(a)
        best = max_range
        for wall, pos, d in ((FENCE[0], x, dx), (-FENCE[0], x, dx), (FENCE[1], y, dy), (-FENCE[1], y, dy)):
            if abs(d) > 1e-6 and (wall - pos) / d > 0:
                best = min(best, (wall - pos) / d)
        for rx, ry, rr in ROCKS:
            along = (rx - x) * dx + (ry - y) * dy
            off2 = (rx - x) ** 2 + (ry - y) ** 2 - along ** 2
            if along > 0 and off2 < rr ** 2:
                best = min(best, along - math.sqrt(rr ** 2 - off2))
        out.append(round(max(0.2, best + random.gauss(0, 0.03)), 2))
    return out


def rover_step(dt, scan_now):
    x, y, heading, speed = r_x.value, r_y.value, r_heading.value, rover["v"]      # speed is signed: negative is reverse
    mission, mode = r_mission.value, r_mode.value
    drives_on = r_left.on.value and r_right.on.value
    want, turn = 0.0, 0.0
    if r_estop.value or not drives_on:
        pass
    elif mode == "MANUAL":
        fresh = time.monotonic() - rover["joy_at"] < 0.5      # a stick that stops reporting counts as centred
        want = (r_joy_y.value if fresh else 0.0) * ROVER_VMAX
        turn = (r_joy_x.value if fresh else 0.0) * 70
        heading = (heading + turn * dt) % 360
        x += math.sin(math.radians(heading)) * speed * dt
        y += math.cos(math.radians(heading)) * speed * dt
    elif mode == "AUTO" and mission != "DOCKED":
        target = ROVER_DOCK if mission == "RETURN" else ROVER_ROUTE[rover["wp"]]
        err = abs(wrap180(bearing(target[0] - x, target[1] - y) - heading))
        want = r_cruise.value * (0.3 if err > 25 else 1.0) * clamp((r_clearance.value - 0.6) / 2.5, 0.25, 1.0)
        x, y, heading, turn = step_toward((x, y), heading, target, speed, 75, dt)
        if math.hypot(target[0] - x, target[1] - y) < 0.8:
            if mission == "RETURN":
                r_mission.set("DOCKED")
                rover["docked_for"] = 0.0
            elif rover["wp"] + 1 < len(ROVER_ROUTE):
                rover["wp"] += 1
                r_mission.set("SURVEY")
            else:
                r_mission.set("RETURN")
    speed = rover["v"] = approach(speed, want, 1.8 * dt)
    r_x.set(x)
    r_y.set(y)
    r_heading.set(heading)
    r_speed.set(abs(speed))
    r_odometer.set(r_odometer.value + abs(speed) * dt)
    r_coverage.set(100 * rover["wp"] / (len(ROVER_ROUTE) - 1) if mission in ("SURVEY", "RETURN") else
                   100.0 if mission == "DOCKED" and rover["wp"] else 0.0)
    # what the survey instrument sees: a quiet field with two buried anomalies
    r_reading.set(22 + 70 * math.exp(-((x - 8) ** 2 + (y - 4) ** 2) / 45) + 40 * math.exp(-((x + 15) ** 2 + (y + 9) ** 2) / 30)
                  + random.gauss(0, 0.6))

    stop = "E-stop is pressed" if r_estop.value else "battery is critical" if r_batt.critical else None
    for motor, side in ((r_left, 1), (r_right, -1)):
        motor.inhibit = stop
        motor.demand = clamp(abs(speed) / ROVER_VMAX + side * turn / 75 * 0.25, 0.0, 1.0)
    docked = mission == "DOCKED"
    r_batt.load_w = 9 + 32 * (r_left.rpm.value + r_right.rpm.value) / 6000
    r_batt.charge_w = 260 if docked else 0.0
    if docked:      # recharge, then go again, so the demo never sits idle
        rover["docked_for"] += dt
        if rover["docked_for"] > 12 and r_batt.soc.value > 90 and not r_estop.value and mode == "AUTO":
            rover_start()

    if scan_now:
        scan = lidar_scan(x, y, heading)
        r_scan.set(json.dumps(scan))
        mid = len(scan) // 2
        r_lidar.true_range = scan[mid]
        r_clearance.set(min(scan[mid - 5: mid + 6]))


# ==================================================================== DRONE
HOME = (0.0, 0.0)
SITE = (45.0, 30.0)     # what the drone is inspecting
DRONE_VMAX = 8.0

d_x = eng.channel("drone.x", label="Drone east", unit="m", precision=1)
d_y = eng.channel("drone.y", label="Drone north", unit="m", precision=1)
d_alt = eng.channel("drone.alt", label="Altitude", unit="m", precision=1, min=0, max=60, warn_high=55)
d_alt_set = eng.channel("drone.alt_set", label="Target Altitude", unit="m", min=5, max=50, step=1, precision=0,
                        writable=True, initial=30)
d_climb = eng.channel("drone.climb", label="Climb Rate", unit="m/s", precision=1, min=-4, max=4)
d_roll = eng.channel("drone.roll", label="Roll", unit="°", precision=1)
d_pitch = eng.channel("drone.pitch", label="Pitch", unit="°", precision=1)
d_heading = eng.channel("drone.heading", label="Heading", unit="°", precision=0)
d_speed = eng.channel("drone.speed", label="Ground Speed", unit="m/s", precision=1, min=0, max=10)
d_wind = eng.channel("drone.wind", label="Wind", unit="m/s", precision=1, min=0, max=15, warn_high=9, alarm_high=12)
d_sats = eng.channel("drone.sats", label="GPS Satellites", precision=0, warn_low=7)
d_home = eng.channel("drone.home", label="Distance Home", unit="m", precision=0)
d_phase = eng.channel("drone.phase", "enum", label="Flight Phase",
                      options=["GROUNDED", "TAKEOFF", "SURVEY", "RETURN", "LANDING"],
                      states={"GROUNDED": "off", "TAKEOFF": "info", "SURVEY": "ok", "RETURN": "warn", "LANDING": "info"},
                      initial="TAKEOFF")
d_pattern = eng.channel("drone.pattern", "enum", label="Pattern", options=["ORBIT", "GRID", "HOVER"], writable=True)

rotors = [Motor(eng, f"rotor{n}", name, full_rpm=9000, max_current=22)
          for n, name in ((1, "Rotor FL"), (2, "Rotor FR"), (3, "Rotor RL"), (4, "Rotor RR"))]
d_batt = Battery(eng, "drone_batt", "Flight Battery", capacity_wh=38, cells=4, low=30, critical=15)
d_gimbal = Servo(eng, "gimbal", "Gimbal Pitch", slew=90)
d_cam = Camera(eng, "drone_cam", "Gimbal Camera")
d_link = Radio(eng, "drone_link", "Telemetry Link", max_mw=500)
d_heat = Heater(eng, "batt_heat", "Battery Heater", target_c=32, ready_c=24, max_c=60)

drone = {"t": 0.0, "grid": 0, "grounded_for": 0.0}
DRONE_GRID = [(SITE[0] + dx, SITE[1] + dy) for n, dy in enumerate((-18, -6, 6, 18)) for dx in ((-26, 26) if n % 2 == 0 else (26, -26))]


@eng.command("drone.takeoff", label="Take Off", confirm=True)
def drone_takeoff():
    if d_phase.value != "GROUNDED":
        raise WriteRejected("The drone is already flying")
    if d_batt.low:
        raise WriteRejected("Flight battery is too low to take off")
    if d_wind.value >= 12:
        raise WriteRejected("Wind is above the take-off limit")
    for m in rotors:
        m.on.set(True)
    d_phase.set("TAKEOFF")


@eng.command("drone.rtl", label="Return Home")
def drone_rtl():
    if d_phase.value in ("TAKEOFF", "SURVEY"):
        d_phase.set("RETURN")


@eng.command("drone.land", label="Land Now", danger=True)
def drone_land():
    if d_phase.value != "GROUNDED":
        d_phase.set("LANDING")


def drone_step(dt):
    drone["t"] += dt
    t = drone["t"]
    x, y, alt, heading, speed = d_x.value, d_y.value, d_alt.value, d_heading.value, d_speed.value
    phase = d_phase.value
    wind = clamp(4.0 + 2.4 * math.sin(t / 19) + 1.1 * math.sin(t / 4.3) + random.gauss(0, 0.1), 0, 15)
    gust = (wind / 15) * math.sin(t * 1.7), (wind / 15) * math.cos(t * 2.3)
    climb, turn, want = 0.0, 0.0, 0.0

    if phase == "TAKEOFF":
        climb = 3.0
        if alt >= d_alt_set.value - 0.3:
            d_phase.set("SURVEY")
    elif phase == "SURVEY":
        climb = clamp((d_alt_set.value - alt) * 1.2, -2.0, 2.5)
        pattern = d_pattern.value
        if pattern == "ORBIT":
            ahead = math.atan2(x - SITE[0], y - SITE[1]) + 0.5        # a point further round the circle
            target, want = (SITE[0] + 26 * math.sin(ahead), SITE[1] + 26 * math.cos(ahead)), 7.0
        elif pattern == "GRID":
            target, want = DRONE_GRID[drone["grid"]], 6.0
            if math.hypot(target[0] - x, target[1] - y) < 2.5:
                drone["grid"] = (drone["grid"] + 1) % len(DRONE_GRID)
        else:
            target, want = (x, y), 0.0
        if want:
            x, y, heading, turn = step_toward((x, y), heading, target, speed, 55, dt)
        if d_batt.low:
            d_phase.set("RETURN")
            eng.alert("drone:battery", "Flight battery low: the drone is returning home", "warn", source="drone")
    elif phase == "RETURN":
        climb = clamp((d_alt_set.value - alt) * 1.2, -2.0, 2.5)
        far = math.hypot(x - HOME[0], y - HOME[1])
        want = clamp(far * 0.8, 0.0, DRONE_VMAX)
        x, y, heading, turn = step_toward((x, y), heading, HOME, speed, 55, dt)
        if far < 1.5:
            d_phase.set("LANDING")
    elif phase == "LANDING":
        climb = -1.6
        if alt <= 0.05:
            alt = 0.0
            d_phase.set("GROUNDED")
            drone["grounded_for"] = 0.0
            for m in rotors:
                m.on.set(False)
    else:   # GROUNDED: fit a fresh pack, then fly again, so the demo never sits idle
        drone["grounded_for"] += dt
        if drone["grounded_for"] > 6:
            d_batt.soc.set(100.0)
            eng.clear_alert("drone:battery")
        if drone["grounded_for"] > 10 and d_wind.value < 11 and not d_batt.low:
            drone_takeoff()

    flying = d_phase.value != "GROUNDED"
    speed = approach(speed, want, 3.0 * dt)
    alt = max(0.0, alt + climb * dt) if flying else 0.0
    roll = clamp(turn * 0.45 + gust[0] * 9, -40, 40) if flying else 0.0
    pitch = clamp(-speed * 1.4 - climb * 0.6 + gust[1] * 7, -30, 30) if flying else 0.0
    d_x.set(x)
    d_y.set(y)
    d_alt.set(alt)
    d_climb.set(climb if flying else 0.0)
    d_roll.set(approach(d_roll.value, roll, 90 * dt))
    d_pitch.set(approach(d_pitch.value, pitch, 60 * dt))
    d_heading.set(heading)
    d_speed.set(speed)
    d_wind.set(wind)
    d_sats.set(14 + round(2 * math.sin(t / 31)))
    d_home.set(math.hypot(x - HOME[0], y - HOME[1]))

    base = (0.56 + climb * 0.07 + speed * 0.012) if flying else 0.0
    for motor, (front, left) in zip(rotors, ((1, 1), (1, -1), (-1, 1), (-1, -1))):
        motor.inhibit = "flight battery is critical" if d_batt.critical and not flying else None
        motor.demand = clamp(base - front * d_pitch.value * 0.004 + left * d_roll.value * 0.004, 0.0, 1.0)
    d_batt.load_w = (150 + 45 * abs(climb) + 2.2 * speed ** 2) if flying else 4.0
    d_link.distance = math.hypot(x, y, alt) * 5 + 60      # scaled up, so the link visibly weakens with range
    d_link.interference = clamp((wind - 6) / 25, 0, 0.4)
    d_heat.ambient = 16 - alt * 0.22
    # the tracker sees the site when the drone is near it and the gimbal looks down
    near = clamp(1 - math.hypot(x - SITE[0], y - SITE[1]) / 40, 0, 1)
    d_cam.target = near * clamp(d_gimbal.position.value / 60, 0, 1) if flying else 0.0


# =============================================================== SUB + BOAT
SUB_TRACK = 40.0           # the sub surveys east-west between -40 and +40 m
SEABED_THINGS = [(-22.0, 6.0), (4.0, -5.0), (19.0, 8.0), (31.0, -3.0)]   # x, y of things the sonar picks up


def seabed(x):
    return 62 + 10 * math.sin(x / 14) + 4 * math.sin(x / 5 + 1)


s_x = eng.channel("sub.x", label="ROV east", unit="m", precision=1, initial=-30)
s_y = eng.channel("sub.y", label="ROV north", unit="m", precision=1)
s_heading = eng.channel("sub.heading", label="ROV Heading", unit="°", precision=0, initial=90)
s_depth = eng.channel("sub.depth", label="Depth", unit="m", precision=1, min=0, max=80, warn_high=68, alarm_high=75)
s_depth_set = eng.channel("sub.depth_set", label="Target Depth", unit="m", min=0, max=70, step=1, precision=0,
                          writable=True, initial=48)
s_seabed = eng.channel("sub.seabed", label="Seabed", unit="m", precision=1)
s_alt = eng.channel("sub.alt", label="Height Above Seabed", unit="m", precision=1, warn_low=4, alarm_low=2, initial=60)
s_phase = eng.channel("sub.phase", "enum", label="Dive Phase", options=["SURFACE", "DIVING", "SURVEY", "ASCENDING", "EMERGENCY"],
                      states={"SURFACE": "off", "DIVING": "info", "SURVEY": "ok", "ASCENDING": "info", "EMERGENCY": "alarm"},
                      initial="DIVING")
s_leak = eng.channel("sub.leak", "bool", label="Hull Leak", states={})
s_power = eng.channel("sub.tether_power", "bool", label="Tether Power", writable=True, initial=True)
s_tether = eng.channel("sub.tether", label="Tether Out", unit="m", precision=0, min=0, max=120, warn_high=105)
s_tension = eng.channel("sub.tension", label="Tether Tension", unit="N", precision=0, warn_high=420)
s_temp = eng.channel("sub.temp", label="Water Temperature", unit="°C", precision=1)
s_salinity = eng.channel("sub.salinity", label="Salinity", unit="PSU", precision=2)
s_turbidity = eng.channel("sub.turbidity", label="Turbidity", unit="NTU", precision=1, warn_high=8)
s_scan = eng.channel("sub.scan", "text", label="Forward Sonar", urgent=False)

b_x = eng.channel("boat.x", label="Tender east", unit="m", precision=1, initial=-34)
b_y = eng.channel("boat.y", label="Tender north", unit="m", precision=1, initial=-6)
b_heading = eng.channel("boat.heading", label="Tender Heading", unit="°", precision=0, initial=60)
b_speed = eng.channel("boat.speed", label="Tender Speed", unit="m/s", precision=2, min=0, max=2)
b_mode = eng.channel("boat.mode", "enum", label="Tender", options=["HOLDING", "FOLLOWING"],
                     states={"HOLDING": "off", "FOLLOWING": "ok"})

b_port = Motor(eng, "boat_port", "Port Propeller", full_rpm=1800, max_current=30)
b_stbd = Motor(eng, "boat_stbd", "Stbd Propeller", full_rpm=1800, max_current=30)
b_batt = Battery(eng, "boat_batt", "Tender Battery", capacity_wh=2400, cells=12)
s_vert = Motor(eng, "sub_vert", "Vertical Propeller", full_rpm=2400, max_current=16)
s_main = Motor(eng, "sub_main", "Main Propeller", full_rpm=2400, max_current=16)
ballast = Pump(eng, "ballast", "Ballast Pump", full_scale=30, fluid="Seawater", fluids=("Seawater", "Air"))
sampler = Pump(eng, "sampler", "Water Sampler", full_scale=4, controller=False, fluid="Seawater", fluids=("Seawater",))
sonar = RangeSensor(eng, "sonar", "Sonar Altimeter", max_range=70, warn_below=4)
pinger = Beacon(eng, "pinger", "Acoustic Pinger", freq_khz=27)
winch = Servo(eng, "winch", "Tether Winch", slew=12)
shore = Radio(eng, "shore_link", "Shore Link", max_mw=2000)
tether_pm = PowerMeter(eng, "tether_pm", "Tether Power")

sub = {"dir": 1, "surface_for": 0.0}


@s_power.interlock
def _(on):
    if not on and s_depth.value > 1.0:
        return "the ROV is under water; surface it first"


@s_depth_set.interlock
def _(target):
    if s_leak.value:
        return "hull leak: the ROV may only surface"


@eng.command("sub.dive", label="Dive")
def sub_dive():
    if s_leak.value:
        raise WriteRejected("Hull leak: clear it before diving")
    if not s_power.value:
        raise WriteRejected("Tether power is off")
    s_phase.set("DIVING")


@eng.command("sub.surface", label="Surface")
def sub_surface():
    if s_phase.value != "SURFACE":
        s_phase.set("ASCENDING")


@eng.command("sub.emergency", label="Emergency Surface", danger=True)
def sub_emergency():
    s_phase.set("EMERGENCY")
    eng.alert("sub:emergency", "ROV emergency surface", "alarm", source="sub")


@eng.command("sub.leak_test", label="Test Leak Alarm", confirm=True, description="Trip or clear the hull leak sensor.")
def sub_leak_test():
    s_leak.set(not s_leak.value)
    if s_leak.value:
        eng.alert("sub:leak", "Hull leak detected: the ROV is surfacing", "alarm", source="sub")
        s_phase.set("EMERGENCY")
    else:
        eng.clear_alert("sub:leak")


def sonar_fan(x, y, heading, depth, beams=31, fov=120.0, max_range=40.0):
    """Forward-looking sonar: ranges to things on the seabed, left to right."""
    out = [max_range] * beams
    if depth < 2:
        return out
    for tx, ty in SEABED_THINGS:
        dist = math.hypot(tx - x, ty - y, max(0.0, seabed(tx) - depth))
        off = wrap180(bearing(tx - x, ty - y) - heading)
        if dist < max_range and abs(off) < fov / 2:
            k = round((off + fov / 2) / fov * (beams - 1))
            for n in (k - 1, k, k + 1):
                if 0 <= n < beams:
                    out[n] = min(out[n], round(dist + abs(n - k) * 0.8 + random.gauss(0, 0.1), 2))
    return out


def water_step(dt, scan_now):
    x, y, heading, depth = s_x.value, s_y.value, s_heading.value, s_depth.value
    phase = s_phase.value
    floor = seabed(x)
    if phase in ("DIVING", "SURVEY"):
        target = min(s_depth_set.value, floor - 6.0)        # terrain following: stay 6 m off the seabed
    else:
        target = 0.0
    rate = 2.0 if phase == "EMERGENCY" else 0.9
    new_depth = clamp(approach(depth, target, rate * dt), 0.0, floor - 0.5)
    vspeed = (new_depth - depth) / dt
    depth = new_depth
    if phase == "DIVING" and abs(depth - target) < 0.4:
        s_phase.set("SURVEY")
    elif phase in ("ASCENDING", "EMERGENCY") and depth < 0.3:
        if phase == "EMERGENCY":
            eng.clear_alert("sub:emergency")
        s_phase.set("SURFACE")
        sub["surface_for"] = 0.0
    elif phase == "SURFACE":    # after a pause at the surface, dive again, so the demo never sits idle
        sub["surface_for"] += dt
        if sub["surface_for"] > 12 and not s_leak.value and s_power.value:
            s_phase.set("DIVING")

    moving = phase in ("DIVING", "SURVEY") and depth > 3
    if moving:
        if abs(x) > SUB_TRACK:
            sub["dir"] = -1 if x > 0 else 1
        target_xy = (x + sub["dir"] * 10, 6 * math.sin((x + sub["dir"] * 10) / 20))
        x, y, heading, _ = step_toward((x, y), heading, target_xy, 0.6, 20, dt)
    s_x.set(x)
    s_y.set(y)
    s_heading.set(heading)
    s_depth.set(depth)
    s_seabed.set(floor)
    s_alt.set(floor - depth)

    wet = depth > 0.5
    sonar.true_range = floor - depth
    sonar.blocked = None if wet else "the transducer is out of the water"
    # the station switches the sonar off just before surfacing and on again once under water
    if phase in ("ASCENDING", "EMERGENCY") and depth < 1.5 and sonar.emit.value:
        sonar.emit.set(False)
    elif phase == "DIVING" and 1.5 < depth < 2.5 and not sonar.emit.value:
        sonar.emit.set(True)
    live = s_power.value
    for motor, demand in ((s_vert, abs(vspeed) / 2.0 + 0.08 * wet), (s_main, 0.45 if moving else 0.0)):
        motor.inhibit = None if live else "tether power is off"
        motor.demand = clamp(demand, 0.0, 1.0)
    if ballast.mode.value == "Normal":      # the station runs the ballast pump unless the operator holds it
        ballast.setpoint.set(clamp(abs(vspeed) * 26, 0.0, 30.0))
    ballast.fluid.set("Seawater" if vspeed >= 0 else "Air")
    ballast.sim_pressure = 101.3 + depth * 10.05
    sampler.sim_flow = 2.4 if phase == "SURVEY" else 0.0
    sampler.sim_pressure = 101.3 + depth * 10.05

    # the tender follows the ROV from above, keeping a little behind
    bx, by, bh, bs = b_x.value, b_y.value, b_heading.value, b_speed.value
    gap = math.hypot(x - bx, y - by)
    want = clamp((gap - 4.0) * 0.35, 0.0, 1.4)
    bx, by, bh, turn = step_toward((bx, by), bh, (x, y), bs, 25, dt) if gap > 1.5 else (bx, by, bh, 0.0)
    bs = approach(bs, want, 0.5 * dt)
    b_x.set(bx)
    b_y.set(by)
    b_heading.set(bh)
    b_speed.set(bs)
    b_mode.set("FOLLOWING" if bs > 0.08 else "HOLDING")
    for motor, side in ((b_port, 1), (b_stbd, -1)):
        motor.demand = clamp(bs / 1.4 + side * turn / 25 * 0.3, 0.0, 1.0)
    b_batt.load_w = 60 + 380 * (b_port.rpm.value + b_stbd.rpm.value) / 3600 + (220 if live else 0)

    out = math.hypot(gap, depth) * 1.08 + 3
    s_tether.set(out)
    winch.command_pct.set(clamp(out / 120 * 100, 0, 100))
    s_tension.set(45 + 3.2 * depth + 60 * abs(vspeed) + random.gauss(0, 1.5))
    tether_pm.true_w = (140 + 420 * (s_vert.rpm.value + s_main.rpm.value) / 4800) if live else 0.0
    tether_pm.true_v = 300.0 if live else 0.0
    shore.distance = 900 + bx * 2
    s_temp.set(18.5 - 0.11 * depth + random.gauss(0, 0.01))
    s_salinity.set(34.6 + 0.004 * depth + random.gauss(0, 0.003))
    s_turbidity.set(1.8 + 7 * math.exp(-(floor - depth) / 4) + random.gauss(0, 0.05))
    if scan_now:
        s_scan.set(json.dumps(sonar_fan(x, y, heading, depth)))


# ------------------------------------------------------------------ diagram
dg = Diagram(eng, "tether", "Tender and ROV", width=640, height=600)
dg.equipment("shore", 420, 30, 190, 84, "Shore link", on="shore_link.enabled", state="shore_link.state",
             values=["shore_link.quality"])
dg.pipe((340, 72), (420, 72), when=["shore_link.enabled"], kind="signal")
dg.vessel("tender", 40, 20, 300, 120, "Tender", value="boat.speed", state="boat.mode")
dg.pipe((190, 140), (190, 180), kind="data")
dg.equipment("winch", 110, 180, 160, 76, "Winch", kind="motor", state="winch.state", values=["sub.tether"])
dg.pipe((190, 256), (190, 420), when=["sub.tether_power"], kind="power")
dg.valve("power", 190, 322, "sub.tether_power", "Tether power", orient="v", label_pos="right")
dg.gauge("ten", 330, 330, "sub.tension", "TEN")
dg.gauge("depth", 430, 330, "sub.depth", "DEP")
dg.vessel("rov", 40, 420, 300, 130, "ROV", value="sub.alt", state="sub.phase", glow="pinger.output")
dg.pipe((340, 485), (420, 485), when=["ballast.flow"], kind="liquid")
dg.equipment("ballast", 420, 440, 190, 90, "Ballast pump", kind="pump", state="ballast.mode", values=["ballast.flow"])
dg.text(40, 585, "The ROV shows its height above the seabed.", size=12)


# ------------------------------------------------------------- whole fleet
@eng.command("fleet.stop_all", label="Stop All", danger=True, description="E-stop the rover, land the drone, surface the ROV.")
def stop_all():
    rover_estop()
    drone_land()
    sub_emergency()


@eng.on_control_lost
def safe():
    """The operating station went silent: put the hand-driven things somewhere safe."""
    if r_mode.value == "MANUAL":
        r_mode.set("HOLD")


@eng.on_start
def power_up():
    for m in (r_left, r_right, *rotors, b_port, b_stbd, s_vert, s_main):
        m.on.set(True)
    r_lidar.emit.set(True)
    d_link.enabled.set(True)
    shore.enabled.set(True)
    d_gimbal.command_pct.set(70.0)
    d_cam.calibrate(background=0.05, reference=0.6)
    d_cam.armed.set(True)
    pinger.output.set(True)
    sonar.emit.set(False)       # it comes on by itself once the ROV is under water


DEVICES = (r_left, r_right, r_batt, r_lidar, *rotors, d_batt, d_gimbal, d_cam, d_link, d_heat,
           b_port, b_stbd, b_batt, s_vert, s_main, ballast, sampler, sonar, pinger, winch, shore, tether_pm)
ticks = {"n": 0}


@eng.loop(hz=50)
def physics(dt):
    ticks["n"] += 1
    scan_now = ticks["n"] % 5 == 0      # the scans update ten times a second
    rover_step(dt, scan_now)
    drone_step(dt)
    water_step(dt, scan_now)
    for dev in DEVICES:
        dev.step(dt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--browser", action="store_true", help="serve browsers on the network instead of opening a window")
    ap.add_argument("--port", type=int)
    ap.add_argument("--host", help="with the window: 0.0.0.0 also lets other devices connect (give a --port)")
    a = ap.parse_args()
    eng.run(host=a.host, port=a.port, desktop=False if a.browser else None)
