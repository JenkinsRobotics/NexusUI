"""
Station-to-station sync benchmark
=================================

Measures how quickly a change made on one station shows up on another:
station A flips a switch, we time until station B receives the new state.
Also reports A's own acknowledgement time and the telemetry frame rate.

    python apps/sync_benchmark/app.py                         local engine in a separate process
    python apps/sync_benchmark/app.py --url ws://HOST:8000/ws --channel some.bool_channel
                                                              against a running engine (must be in open
                                                              control mode or you must hold control)

Browsers add about one display frame (~8-16 ms) on top of these numbers to paint.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import subprocess
import sys
import time


def serve(port: int) -> None:
    from nexusui import Engine
    eng = Engine("Sync Benchmark", control="open")
    eng.channel("bench.switch", "bool", writable=True)
    wave = eng.channel("bench.wave")
    t0 = time.time()

    @eng.loop(hz=200)
    def _(dt):
        wave.set(math.sin(time.time() - t0))

    eng.run(host="127.0.0.1", port=port, desktop=False, log_level="error")


async def bench(url: str, channel: str, n: int) -> None:
    import websockets

    async with websockets.connect(f"{url}?name=Bench-A") as a, websockets.connect(f"{url}?name=Bench-B") as b:
        hello_a = json.loads(await a.recv())
        await b.recv()
        if hello_a["engine"]["control"] == "lock":
            await a.send(json.dumps({"t": "claim", "id": 0}))
        value = bool(hello_a["values"].get(channel, False))
        seen_b: dict[int, float] = {}
        acks: dict[int, float] = {}
        frames = 0
        expect = {"v": None, "i": None}

        async def read_b():
            nonlocal frames
            async for raw in b:
                now = time.perf_counter()
                m = json.loads(raw)
                if m["t"] == "d":
                    frames += 1
                    if channel in m["v"] and m["v"][channel] == expect["v"] and expect["i"] not in seen_b:
                        seen_b[expect["i"]] = now

        async def read_a():
            async for raw in a:
                m = json.loads(raw)
                if m["t"] == "ack" and m["id"] in sent:
                    acks[m["id"]] = time.perf_counter()

        sent: dict[int, float] = {}
        async def pause(sec):
            # asyncio.sleep() below ~16 ms returns immediately on Windows, so pace with perf_counter
            end = time.perf_counter() + sec
            while time.perf_counter() < end:
                await asyncio.sleep(0)

        tasks = [asyncio.create_task(read_b()), asyncio.create_task(read_a())]
        await pause(0.5)
        frames = 0
        await pause(2.0)                      # idle window: telemetry rate only
        idle_rate = frames / 2.0
        for i in range(1, n + 1):
            value = not value
            expect.update(v=value, i=i)
            sent[i] = time.perf_counter()
            await a.send(json.dumps({"t": "write", "id": i, "ch": channel, "v": value}))
            deadline = time.perf_counter() + 0.5
            while not (i in seen_b and i in acks) and time.perf_counter() < deadline:
                await asyncio.sleep(0)
            await pause(0.02)
        for t in tasks:
            t.cancel()

    def stats(name, xs):
        xs = sorted(xs)
        if not xs:
            print(f"{name:34} no samples")
            return
        q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
        print(f"{name:34} median {statistics.median(xs):6.2f} ms   p95 {q(.95):6.2f} ms   p99 {q(.99):6.2f} ms   max {xs[-1]:6.2f} ms")

    to_b = [(seen_b[i] - sent[i]) * 1000 for i in sent if i in seen_b]
    to_ack = [(acks[i] - sent[i]) * 1000 for i in sent if i in acks]
    print(f"\n{n} toggles, {len(to_b)} seen by station B, {len(to_ack)} acknowledged\n")
    stats("A clicks -> B sees new state", to_b)
    stats("A clicks -> A gets confirmation", to_ack)
    print(f"{'idle telemetry frames at B':34} {idle_rate:6.1f} per second\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="engine WebSocket, e.g. ws://192.168.1.20:8000/ws")
    ap.add_argument("--channel", default="bench.switch", help="writable bool channel to toggle")
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.serve:
        serve(a.port)
        return
    proc = None
    url = a.url
    if not url:
        proc = subprocess.Popen([sys.executable, __file__, "--serve", "--port", str(a.port)])
        url = f"ws://127.0.0.1:{a.port}/ws"
        time.sleep(2.5)
    try:
        asyncio.run(bench(url, a.channel, a.n))
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
