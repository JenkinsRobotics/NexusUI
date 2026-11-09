import type {
  Ack, Alert, ChannelInfo, CommandInfo, Control, DeviceInfo, DiagramInfo, LogEntry, StationInfo, Writer,
} from "./types";

type Fn = () => void;
export type Topic = "conn" | "stats" | "catalog" | "control" | "stations" | "alerts" | "logs" | "toasts" | "layout";
export type ConnState = "connecting" | "open" | "closed";

export interface ChanSnap { value: any; pending: boolean; writer?: Writer; lock?: string }
export interface Toast { id: number; level: "info" | "warn" | "alarm" | "ok"; msg: string }
export interface LayoutEvent { name: string; by?: string; station?: string; deleted?: boolean; n: number }

const HIST_RATE = 10;          // aligned history samples per second
const HIST_SECONDS = 120;
const HIST_CAP = HIST_RATE * HIST_SECONDS;

/** Fixed-size ring of samples, shared timeline for every number channel. */
export class History {
  t = new Float64Array(HIST_CAP);
  cols = new Map<string, Float64Array>();
  start = 0;
  len = 0;
  version = 0;
  epoch = 0;            // counts reloads from the engine (each connect)

  reset(names: string[]) {
    this.cols = new Map(names.map((n) => [n, new Float64Array(HIST_CAP)]));
    this.start = this.len = 0;
    this.version++;
    this.epoch++;
  }
  push(ts: number, values: Map<string, any>) {
    const idx = (this.start + this.len) % HIST_CAP;
    this.t[idx] = ts;
    for (const [name, col] of this.cols) {
      const v = values.get(name);
      col[idx] = typeof v === "number" ? v : NaN;
    }
    if (this.len < HIST_CAP) this.len++;
    else this.start = (this.start + 1) % HIST_CAP;
    this.version++;
  }
  /** Samples newer than `since` (server seconds) for the given channels. */
  slice(names: string[], since: number): { t: number[]; v: (number | null)[][] } {
    const t: number[] = [];
    const v: (number | null)[][] = names.map(() => []);
    const cols = names.map((n) => this.cols.get(n));
    for (let k = 0; k < this.len; k++) {
      const idx = (this.start + k) % HIST_CAP;
      if (this.t[idx] < since) continue;
      t.push(this.t[idx]);
      cols.forEach((c, j) => {
        const x = c ? c[idx] : NaN;
        v[j].push(Number.isFinite(x) ? x : null);
      });
    }
    return { t, v };
  }
}

export class Station {
  url: string;
  status: ConnState = "connecting";
  you: StationInfo | null = null;
  engine: { name: string; control: string; frame_rate: number; watchdog: number } | null = null;
  channels = new Map<string, ChannelInfo>();
  commands = new Map<string, CommandInfo>();
  devices = new Map<string, DeviceInfo>();
  diagrams = new Map<string, DiagramInfo>();
  control: Control = { mode: "lock", holder: null, holder_name: null };
  stations: StationInfo[] = [];
  alerts: Alert[] = [];
  logs: LogEntry[] = [];
  toasts: Toast[] = [];
  layoutEvent: LayoutEvent | null = null;
  values = new Map<string, any>();
  writers = new Map<string, Writer>();
  locks = new Map<string, string>();
  history = new History();
  rtt = NaN;
  offset = 0;           // server time minus local time, seconds
  rate = 0;             // updates received per second
  lastData = 0;

  private ws: WebSocket | null = null;
  private snaps = new Map<string, ChanSnap>();
  private pending = new Map<string, number>();
  private chanSubs = new Map<string, Set<Fn>>();
  private topicSubs = new Map<Topic, Set<Fn>>();
  private versions = new Map<Topic, number>();
  private acks = new Map<number, { resolve: (a: Ack) => void; timer: number }>();
  private nextId = 1;
  private retry = 250;
  private timers: number[] = [];
  private msgCount = 0;
  private toastId = 1;
  private layoutN = 0;

  constructor(url: string) {
    this.url = url;
  }

  // ------------------------------------------------------------ subscriptions
  subscribeChannel = (name: string, fn: Fn) => {
    let s = this.chanSubs.get(name);
    if (!s) this.chanSubs.set(name, (s = new Set()));
    s.add(fn);
    return () => s!.delete(fn);
  };
  channelSnap = (name: string): ChanSnap => {
    let s = this.snaps.get(name);
    if (!s) {
      s = { value: this.values.get(name), pending: false, writer: this.writers.get(name), lock: this.locks.get(name) };
      this.snaps.set(name, s);
    }
    return s;
  };
  subscribe = (topic: Topic, fn: Fn) => {
    let s = this.topicSubs.get(topic);
    if (!s) this.topicSubs.set(topic, (s = new Set()));
    s.add(fn);
    return () => s!.delete(fn);
  };
  version = (topic: Topic) => this.versions.get(topic) ?? 0;

  private emit(topic: Topic) {
    this.versions.set(topic, this.version(topic) + 1);
    this.topicSubs.get(topic)?.forEach((f) => f());
  }
  private touch(name: string) {
    this.snaps.set(name, {
      value: this.values.get(name),
      pending: (this.pending.get(name) ?? 0) > 0,
      writer: this.writers.get(name),
      lock: this.locks.get(name),
    });
    this.chanSubs.get(name)?.forEach((f) => f());
  }

  // ------------------------------------------------------------ connection
  get name() {
    try { return localStorage.getItem("vp.station") ?? ""; } catch { return ""; }
  }

  start() {
    this.open();
    this.timers.push(window.setInterval(() => this.ping(), 250));
    this.timers.push(window.setInterval(() => this.sampleHistory(), 1000 / HIST_RATE));
    this.timers.push(window.setInterval(() => {
      this.rate = this.msgCount;
      this.msgCount = 0;
      this.emit("stats");
    }, 1000));
  }

  stop() {
    this.timers.forEach(clearInterval);
    this.ws?.close();
  }

  private open() {
    this.status = "connecting";
    this.emit("conn");
    const ws = new WebSocket(`${this.url}?name=${encodeURIComponent(this.name)}`);
    this.ws = ws;
    ws.onmessage = (ev) => this.onMessage(JSON.parse(ev.data));
    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.status = "closed";
      this.pending.clear();
      for (const [, a] of this.acks) { clearTimeout(a.timer); a.resolve({ ok: false, error: "Connection lost" }); }
      this.acks.clear();
      this.emit("conn");
      for (const n of this.values.keys()) this.touch(n);
      setTimeout(() => this.open(), this.retry);
      this.retry = Math.min(this.retry * 2, 2000);
    };
  }

  private send(msg: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  private ping() {
    this.send({ t: "ping", id: this.nextId++, ct: performance.now() });
  }

  private sampleHistory() {
    if (this.status !== "open") return;
    this.history.push(Date.now() / 1000 + this.offset, this.values);
  }

  /** Current server time in seconds. */
  now() {
    return Date.now() / 1000 + this.offset;
  }

  // ------------------------------------------------------------ messages
  private onMessage(m: any) {
    this.msgCount++;
    switch (m.t) {
      case "d": {
        this.lastData = performance.now();
        if (m.w) for (const k in m.w) this.writers.set(k, m.w[k]);
        for (const k in m.v) {
          this.values.set(k, m.v[k]);
          this.touch(k);
        }
        break;
      }
      case "pong": {
        const now = performance.now();
        const rtt = now - m.ct;
        this.rtt = Number.isNaN(this.rtt) ? rtt : this.rtt * 0.8 + rtt * 0.2;
        this.offset = m.st - (Date.now() - rtt / 2) / 1000;
        break;
      }
      case "ack": {
        const a = this.acks.get(m.id);
        if (a) {
          clearTimeout(a.timer);
          this.acks.delete(m.id);
          a.resolve({ ok: m.ok, error: m.error });
        }
        break;
      }
      case "hello": this.onHello(m); break;
      case "locks": {
        for (const k in m.v) {
          if (m.v[k]) this.locks.set(k, m.v[k]);
          else this.locks.delete(k);
          this.touch(k);
        }
        break;
      }
      case "control": this.control = m; this.emit("control"); break;
      case "stations": this.stations = m.list; this.emit("stations"); break;
      case "alerts": this.alerts = m.list; this.emit("alerts"); break;
      case "logs": {
        this.logs = [...this.logs, ...m.list].slice(-400);
        this.emit("logs");
        break;
      }
      case "layout": {
        this.layoutEvent = { ...m, n: ++this.layoutN };
        this.emit("layout");
        break;
      }
    }
  }

  private onHello(m: any) {
    this.retry = 250;
    this.you = m.you;
    this.engine = m.engine;
    this.offset = m.ts - Date.now() / 1000;
    this.channels = new Map(m.channels.map((c: ChannelInfo) => [c.name, c]));
    this.commands = new Map(m.commands.map((c: CommandInfo) => [c.name, c]));
    this.devices = new Map(m.devices.map((d: DeviceInfo) => [d.id, d]));
    this.diagrams = new Map((m.diagrams ?? []).map((d: DiagramInfo) => [d.id, d]));
    this.values = new Map(Object.entries(m.values));
    this.writers = new Map(Object.entries(m.writes ?? {}));
    this.locks = new Map(Object.entries(m.locks ?? {}) as [string, string][]);
    this.control = m.control;
    this.stations = m.stations;
    this.alerts = m.alerts;
    this.logs = m.logs;
    this.pending.clear();
    const names = Object.keys(m.history.v);
    this.history.reset(names);
    const hv = m.history.v;
    m.history.t.forEach((ts: number, k: number) => {
      const row = new Map<string, any>(names.map((n) => [n, hv[n][k]]));
      this.history.push(ts, row);
    });
    this.status = "open";
    (["conn", "catalog", "control", "stations", "alerts", "logs"] as Topic[]).forEach((t) => this.emit(t));
    for (const n of this.values.keys()) this.touch(n);
  }

  // ------------------------------------------------------------ actions
  private request(msg: Record<string, unknown>, channel?: string): Promise<Ack> {
    const id = this.nextId++;
    return new Promise<Ack>((resolve) => {
      if (!this.send({ ...msg, id })) {
        resolve({ ok: false, error: "Not connected" });
        return;
      }
      if (channel) {
        this.pending.set(channel, (this.pending.get(channel) ?? 0) + 1);
        this.touch(channel);
      }
      const timer = window.setTimeout(() => {
        this.acks.delete(id);
        resolve({ ok: false, error: "No reply from engine within 5 s" });
      }, 5000);
      this.acks.set(id, { resolve, timer });
    }).then((ack) => {
      if (channel) {
        this.pending.set(channel, Math.max(0, (this.pending.get(channel) ?? 1) - 1));
        this.touch(channel);
      }
      if (!ack.ok) this.toast(ack.error ?? "Rejected", "alarm");
      return ack;
    });
  }

  write(channel: string, value: unknown) {
    return this.request({ t: "write", ch: channel, v: value }, channel);
  }
  command(name: string, args?: Record<string, unknown>) {
    return this.request({ t: "cmd", name, args });
  }
  claim(force = false) {
    return this.request({ t: "claim", force });
  }
  release() {
    return this.request({ t: "release" });
  }
  setOverride(on: boolean) {
    return this.request({ t: "override", on });
  }
  ackAlerts(ids: number[] | "all") {
    this.send({ t: "ack_alerts", ids });
  }
  clearAlerts() {
    this.send({ t: "clear_alerts" });
  }
  rename(name: string) {
    try { localStorage.setItem("vp.station", name); } catch { /* storage blocked */ }
    this.send({ t: "rename", name });
  }

  toast(msg: string, level: Toast["level"] = "info") {
    const t = { id: this.toastId++, level, msg };
    this.toasts = [...this.toasts.slice(-3), t];
    this.emit("toasts");
    setTimeout(() => {
      this.toasts = this.toasts.filter((x) => x.id !== t.id);
      this.emit("toasts");
    }, level === "alarm" ? 6000 : 3500);
  }

  // ------------------------------------------------------------ helpers
  /** Interlocks are overridden and this station is the one operating. */
  get bypass() {
    return !!this.control.override && this.inControl;
  }

  get inControl() {
    return this.control.mode === "open" || (!!this.you && this.control.holder === this.you.id);
  }
}
