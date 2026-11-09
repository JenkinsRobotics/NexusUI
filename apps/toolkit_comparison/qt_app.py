"""The bench supply panel of app.py, written in PyQt6.  (pip install PyQt6)

Run:  python apps/toolkit_comparison/qt_app.py
"""
import random
import sys
from collections import deque

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

LOAD_OHMS, TRIP_C, RESET_C = 8.0, 85.0, 50.0
COLORS = {"v": "#5aa2ff", "i": "#f5a623", "t": "#3ddc97"}
SCALE = {"v": 24, "i": 4, "t": 100}


class Chart(QWidget):
    def __init__(self, history):
        super().__init__()
        self.history = history
        self.setMinimumHeight(260)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#111111"))
        w, h = self.width(), self.height()
        for key, data in self.history.items():
            if len(data) > 1:
                p.setPen(QPen(QColor(COLORS[key]), 2))
                p.drawPolyline(QPolygonF([QPointF(w * n / 599, h - h * y / SCALE[key]) for n, y in enumerate(data)]))


class Panel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bench Supply")
        self.v, self.i, self.t, self.tripped, self.n = 0.0, 0.0, 25.0, False, 0
        self.history = {k: deque(maxlen=600) for k in "vit"}
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.readouts = {}
        for key, name, unit in [("v", "Voltage", "V"), ("i", "Current", "A"), ("t", "Temperature", "°C")]:
            box = QGroupBox(name)
            inner = QVBoxLayout(box)
            self.readouts[key] = QLabel("-", alignment=Qt.AlignmentFlag.AlignCenter)
            self.readouts[key].setFont(QFont("Menlo", 28))
            inner.addWidget(self.readouts[key])
            inner.addWidget(QLabel(unit, alignment=Qt.AlignmentFlag.AlignCenter))
            top.addWidget(box)
        layout.addLayout(top)

        controls = QHBoxLayout()
        self.output = QCheckBox("Output")
        self.vset = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=240, value=120)
        self.set_lbl = QLabel()
        self.fan = QComboBox()
        self.fan.addItems(["AUTO", "LOW", "HIGH"])
        self.status = QLabel("IDLE")
        reset = QPushButton("Reset Trip", clicked=self.reset_trip)
        for w in (self.output, QLabel("Setpoint"), self.vset, self.set_lbl, QLabel("Fan"), self.fan, self.status):
            controls.addWidget(w)
        controls.addStretch()
        controls.addWidget(reset)
        layout.addLayout(controls)

        self.chart = Chart(self.history)
        layout.addWidget(self.chart, 1)
        self.timer = QTimer(self, timeout=self.tick, interval=20)
        self.timer.start()

    def reset_trip(self):
        if self.t > RESET_C:
            QMessageBox.warning(self, "Reset Trip", f"Board is still above {RESET_C:g} °C")
            return
        self.tripped = False
        self.output.setEnabled(True)

    def tick(self):
        dt = 0.02
        target = self.vset.value() / 10 if self.output.isChecked() else 0.0
        v = self.v + (target - self.v) * min(1.0, dt / 0.15)
        i = v / LOAD_OHMS * (1 + random.gauss(0, 0.004)) if v > 0.01 else 0.0
        t = self.t
        airflow = {"LOW": 0.3, "HIGH": 1.0}.get(self.fan.currentText(), min(1.0, max(0.2, (t - 40) / 20)))
        t += (v * i * 0.9 - (t - 25) * (0.4 + 1.6 * airflow)) * dt / 6
        self.v, self.i, self.t = v, i, t
        if t >= TRIP_C and not self.tripped:
            self.tripped = True
            self.output.setChecked(False)
            self.output.setEnabled(False)
        self.readouts["v"].setText(f"{v:.2f}")
        self.readouts["i"].setText(f"{i:.2f}")
        self.readouts["t"].setText(f"{t:.1f}")
        self.readouts["t"].setStyleSheet("color: red" if t >= 80 else "color: orange" if t >= 65 else "")
        self.set_lbl.setText(f"{self.vset.value() / 10:.1f} V")
        self.status.setText("FAULT" if self.tripped else "RUNNING" if self.output.isChecked() else "IDLE")
        self.n += 1
        if self.n % 5 == 0:
            for key, value in (("v", v), ("i", i), ("t", t)):
                self.history[key].append(value)
            self.chart.update()


app = QApplication(sys.argv)
win = Panel()
win.resize(900, 520)
win.show()
# --- bench: instrumentation for run.py (not part of the app, not counted as code)
import os, statistics, time
if "BENCH_SECS" in os.environ:
    win.output.setChecked(True); win.vset.setValue(200); win.fan.setCurrentText("HIGH")
    lat = []
    def ready():
        if not win.windowHandle().isExposed():
            return QTimer.singleShot(1, ready)
        app.processEvents()
        print(f"READY {time.time():.4f}", flush=True)
    ready()
    def ping():
        t0 = time.perf_counter()
        QTimer.singleShot(0, lambda: lat.append((time.perf_counter() - t0) * 1000))
        QTimer.singleShot(200, ping)
    ping()
    def done():
        xs = sorted(lat)
        print(f"DISPATCH median {statistics.median(xs):.3f} ms p95 {xs[int(.95 * len(xs))]:.3f} ms n={len(xs)}", flush=True)
        app.quit()
    QTimer.singleShot(int(float(os.environ["BENCH_SECS"]) * 1000), done)
# --- end bench
sys.exit(app.exec())
