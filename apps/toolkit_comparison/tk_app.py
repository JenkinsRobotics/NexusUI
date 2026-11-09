"""The bench supply panel of app.py, written in Tkinter.

Run:  python apps/toolkit_comparison/tk_app.py
"""
import random
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

LOAD_OHMS, TRIP_C, RESET_C = 8.0, 85.0, 50.0
COLORS = {"v": "#5aa2ff", "i": "#f5a623", "t": "#3ddc97"}
SCALE = {"v": 24, "i": 4, "t": 100}

root = tk.Tk()
root.title("Bench Supply")
output = tk.BooleanVar()
vset = tk.DoubleVar(value=12.0)
fan = tk.StringVar(value="AUTO")
state = {"v": 0.0, "i": 0.0, "t": 25.0, "tripped": False, "n": 0}
history = {k: deque(maxlen=600) for k in "vit"}

top = ttk.Frame(root, padding=12)
top.pack(fill="x")
readouts = {}
for col, (key, name, unit) in enumerate([("v", "Voltage", "V"), ("i", "Current", "A"), ("t", "Temperature", "°C")]):
    box = ttk.LabelFrame(top, text=name, padding=8)
    box.grid(row=0, column=col, padx=6, sticky="ew")
    top.columnconfigure(col, weight=1)
    readouts[key] = tk.Label(box, text="-", font=("Menlo", 28))
    readouts[key].pack()
    ttk.Label(box, text=unit).pack()
normal_fg = readouts["t"].cget("fg")

controls = ttk.Frame(root, padding=12)
controls.pack(fill="x")
out_btn = ttk.Checkbutton(controls, text="Output", variable=output)
out_btn.pack(side="left")
ttk.Label(controls, text="   Setpoint").pack(side="left")
ttk.Scale(controls, from_=0, to=24, variable=vset, length=240).pack(side="left", padx=6)
set_lbl = ttk.Label(controls, width=7)
set_lbl.pack(side="left")
ttk.Label(controls, text="   Fan").pack(side="left")
ttk.Combobox(controls, textvariable=fan, values=["AUTO", "LOW", "HIGH"], width=6, state="readonly").pack(side="left", padx=6)
status = ttk.Label(controls, text="IDLE", width=9)
status.pack(side="left", padx=12)


def reset_trip():
    if state["t"] > RESET_C:
        messagebox.showwarning("Reset Trip", f"Board is still above {RESET_C:g} °C")
        return
    state["tripped"] = False
    out_btn.state(["!disabled"])


ttk.Button(controls, text="Reset Trip", command=reset_trip).pack(side="right")

chart = tk.Canvas(root, height=260, background="#111111", highlightthickness=0)
chart.pack(fill="both", expand=True, padx=12, pady=12)


def draw_chart():
    w, h = chart.winfo_width(), chart.winfo_height()
    chart.delete("all")
    for key, data in history.items():
        if len(data) > 1:
            points = [c for n, y in enumerate(data) for c in (w * n / 599, h - h * y / SCALE[key])]
            chart.create_line(points, fill=COLORS[key], width=2)


def tick():
    dt = 0.02
    target = vset.get() if output.get() else 0.0
    v = state["v"] + (target - state["v"]) * min(1.0, dt / 0.15)
    i = v / LOAD_OHMS * (1 + random.gauss(0, 0.004)) if v > 0.01 else 0.0
    t = state["t"]
    airflow = {"LOW": 0.3, "HIGH": 1.0}.get(fan.get(), min(1.0, max(0.2, (t - 40) / 20)))
    t += (v * i * 0.9 - (t - 25) * (0.4 + 1.6 * airflow)) * dt / 6
    state.update(v=v, i=i, t=t)
    if t >= TRIP_C and not state["tripped"]:
        state["tripped"] = True
        output.set(False)
        out_btn.state(["disabled"])
    readouts["v"].config(text=f"{v:.2f}")
    readouts["i"].config(text=f"{i:.2f}")
    readouts["t"].config(text=f"{t:.1f}", fg="red" if t >= 80 else "orange" if t >= 65 else normal_fg)
    set_lbl.config(text=f"{vset.get():.1f} V")
    status.config(text="FAULT" if state["tripped"] else "RUNNING" if output.get() else "IDLE")
    state["n"] += 1
    if state["n"] % 5 == 0:
        for key in "vit":
            history[key].append(state[key])
        draw_chart()
    root.after(20, tick)


tick()
# --- bench: instrumentation for run.py (not part of the app, not counted as code)
import os, statistics, time
if "BENCH_SECS" in os.environ:
    output.set(True); vset.set(20.0); fan.set("HIGH")
    root.update()
    print(f"READY {time.time():.4f}", flush=True)
    lat = []
    def ping():
        t0 = time.perf_counter()
        root.after(0, lambda: lat.append((time.perf_counter() - t0) * 1000))
        root.after(200, ping)
    ping()
    def done():
        xs = sorted(lat)
        print(f"DISPATCH median {statistics.median(xs):.3f} ms p95 {xs[int(.95 * len(xs))]:.3f} ms n={len(xs)}", flush=True)
        root.destroy()
    root.after(int(float(os.environ["BENCH_SECS"]) * 1000), done)
# --- end bench
root.mainloop()
