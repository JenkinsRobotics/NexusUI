"""
Toolkit comparison: measure the same panel in Tkinter, PyQt6, Rust and NexusUI
================================================================================

    python apps/toolkit_comparison/run.py [--toolkit-python PATH] [--port 8041]

Needs PyQt6 for the Qt panel and the dev extra for the NexusUI one. If PyQt6
lives in another environment, point --toolkit-python at that interpreter. The two Rust
panels are measured when they have been built with `cargo build --release`:
    rust_app/      all Rust: a native egui screen, no web view
    rust_engine/   a Rust engine serving the same React UI as app.py

For each panel it reports:
  code      lines of code, without blanks, comments and the bench block
  startup   launch to the first painted frame (Tkinter, PyQt6), or to the UI being
            connected and showing data (NexusUI, in a standalone window)
  CPU, memory   over 10 s while every readout and the chart update live
  input     time for an event to reach its handler. Tkinter and PyQt6: a posted event
            under load. Rust/egui: a repaint request until the next frame runs. The two
            React-screen panels: a write from one station until it is confirmed, and
            until a second station sees it.

The React-screen figures include the web view's helper processes. Finding those is
macOS-specific; on other systems only the engine process is counted. Another program
using a web view heavily at the same time shows up as more than 4 processes: rerun.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def count_code(path: Path, comment: str = "#") -> int:
    """Lines of code: no blanks, comments, module docstring or bench block."""
    n, in_bench, in_doc = 0, False, False
    for line in path.read_text("utf-8").splitlines():
        s = line.strip()
        if in_doc or (n == 0 and s.startswith('"""')):
            in_doc = not (s.endswith('"""') and (in_doc or len(s) > 3))
        elif s.startswith(f"{comment} --- bench"):
            in_bench = True
        elif s.startswith(f"{comment} --- end bench"):
            in_bench = False
        elif not in_bench and s and not s.startswith(comment):
            n += 1
    return n


def ps(pids) -> dict[int, tuple[float, float]]:
    """{pid: (memory MB, CPU seconds so far)} for the pids still alive."""
    out = subprocess.run(["ps", "-o", "pid=,rss=,cputime=", "-p", ",".join(map(str, pids))],
                         capture_output=True, text=True).stdout
    res = {}
    for line in out.splitlines():
        pid, rss, cpu = line.split()
        parts = [float(x) for x in cpu.replace("-", ":").split(":")]
        res[int(pid)] = (int(rss) / 1024, sum(x * 60 ** n for n, x in enumerate(reversed(parts))))
    return res


def webkit_pids() -> set[int]:
    if sys.platform != "darwin":
        return set()
    out = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True).stdout
    return {int(line.split(None, 1)[0]) for line in out.splitlines() if "com.apple.WebKit" in line}


def sample(pids, label: str) -> None:
    time.sleep(3)
    a = ps(pids)
    time.sleep(10)
    b = ps(pids)
    cpu = sum(b[p][1] - a[p][1] for p in b if p in a) / 10 * 100
    print(f"  {label:34} CPU {cpu:5.1f} % of one core, memory {sum(v[0] for v in b.values()):4.0f} MB")


def toolkit(name: str, cmd: list[str], lines: int, input_label: str = "input: posted event to handler") -> None:
    """Measure a panel that prints READY <epoch> after its first frame and a DISPATCH line on exit."""
    print(f"== {name}   ({lines} lines of code)")
    starts = []
    for _ in range(3):
        t0 = time.time()
        p = subprocess.Popen(cmd, env={**os.environ, "BENCH_SECS": "1"}, stdout=subprocess.PIPE, text=True, cwd=HERE)
        starts.append(float(p.stdout.readline().split()[1]) - t0)
        p.wait()
    print(f"  startup                            {statistics.median(starts):.2f} s  (runs: {', '.join(f'{s:.2f}' for s in starts)})")
    p = subprocess.Popen(cmd, env={**os.environ, "BENCH_SECS": "16"}, stdout=subprocess.PIPE, text=True, cwd=HERE)
    p.stdout.readline()
    sample([p.pid], "live updates")
    dispatch = next((l for l in p.stdout.read().splitlines() if l.startswith("DISPATCH ")), "DISPATCH not reported")
    print(f"  {input_label:34} {dispatch.removeprefix('DISPATCH ')}")
    p.wait()


def stations(port: int) -> int:
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=0.5))["stations"]
    except Exception:
        return 0


async def write_all(port: int, values: dict) -> None:
    import websockets
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws?name=Setup", max_size=None) as ws:
        await ws.recv()
        for i, (ch, v) in enumerate(values.items()):
            await ws.send(json.dumps({"t": "write", "id": i, "ch": ch, "v": v}))
        await asyncio.sleep(0.3)


async def write_latency(port: int, n: int = 200) -> None:
    import websockets
    url = f"ws://127.0.0.1:{port}/ws"
    async with websockets.connect(url + "?name=A", max_size=None) as a, websockets.connect(url + "?name=B", max_size=None) as b:
        await a.recv()
        await b.recv()
        acks, seen, sent, expect = {}, {}, {}, {"v": None, "i": None}

        async def read_a():
            async for raw in a:
                m = json.loads(raw)
                if m["t"] == "ack" and m["ok"]:
                    acks[m["id"]] = time.perf_counter()

        async def read_b():
            async for raw in b:
                now = time.perf_counter()
                m = json.loads(raw)
                if m["t"] == "d" and expect["i"] and m["v"].get("board.fan") == expect["v"] and expect["i"] not in seen:
                    seen[expect["i"]] = now

        tasks = [asyncio.create_task(read_a()), asyncio.create_task(read_b())]
        for i in range(1, n + 1):
            value = "LOW" if i % 2 else "HIGH"
            expect.update(v=value, i=i)
            sent[i] = time.perf_counter()
            await a.send(json.dumps({"t": "write", "id": i, "ch": "board.fan", "v": value}))
            end = time.perf_counter() + 0.5
            while not (i in seen and i in acks) and time.perf_counter() < end:
                await asyncio.sleep(0)
            await asyncio.sleep(0.02)
        for t in tasks:
            t.cancel()
    for label, got in (("input: write to confirmed", acks), ("input: write to a second station", seen)):
        xs = sorted((got[i] - sent[i]) * 1000 for i in sent if i in got)
        print(f"  {label:34} median {statistics.median(xs):.3f} ms p95 {xs[int(.95 * len(xs))]:.3f} ms n={len(xs)}")


def station(title: str, cmd: list[str], port: int) -> None:
    """Measure a panel whose screen is the React UI in a standalone window (any engine language)."""
    print(f"== {title}")
    with socket.socket() as s:      # fail loudly if the port is not really free
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # as the servers do; a just-closed port is fine
        s.bind(("0.0.0.0", port))

    def launch():
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while not stations(port):
            if p.poll() is not None:
                sys.exit(f"{cmd[0]} exited before its window connected")
            time.sleep(0.01)
        return p

    starts = []
    for _ in range(3):
        t0 = time.time()
        p = launch()
        starts.append(time.time() - t0)
        p.terminate()
        p.wait()
        time.sleep(1.0)
    print(f"  startup                            {statistics.median(starts):.2f} s  (runs: {', '.join(f'{s:.2f}' for s in starts)})")
    before = webkit_pids()
    p = launch()
    asyncio.run(write_all(port, {"psu.vset": 20.0, "board.fan": "HIGH", "psu.output": True}))
    time.sleep(1.5)
    helpers = sorted(webkit_pids() - before)
    sample([p.pid], "live updates, engine alone")
    sample([p.pid] + helpers, f"live updates, engine + web view ({1 + len(helpers)} processes)")
    asyncio.run(write_latency(port))
    p.terminate()
    p.wait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--toolkit-python", default=sys.executable, help="interpreter that has tkinter and PyQt6")
    ap.add_argument("--port", type=int, default=8041)
    a = ap.parse_args()
    toolkit("Tkinter", [a.toolkit_python, "tk_app.py"], count_code(HERE / "tk_app.py"))
    toolkit("PyQt6", [a.toolkit_python, "qt_app.py"], count_code(HERE / "qt_app.py"))
    rust_bin = HERE / "rust_app" / "target" / "release" / "bench-panel"
    if rust_bin.exists():
        toolkit("Rust + egui (native, no web view)", [str(rust_bin)], count_code(HERE / "rust_app" / "src" / "main.rs", "//"),
                "input: handled on the next frame")
    else:
        print("== Rust + egui: not built. Run: cd apps/toolkit_comparison/rust_app && cargo build --release")
    rust_engine = HERE / "rust_engine" / "target" / "release" / "bench-engine"
    if rust_engine.exists():
        station("Rust engine + the same React UI, standalone window", [str(rust_engine), "--desktop", "--port", str(a.port)], a.port)
    else:
        print("== Rust engine + React UI: not built. Run: cd apps/toolkit_comparison/rust_engine && cargo build --release")
    station(f"NexusUI (Python engine + React UI), standalone window   ({count_code(HERE / 'app.py')} lines of code, layout made in the editor)",
            [sys.executable, str(HERE / "app.py"), "--port", str(a.port)], a.port)
