/**
 * Widget kit: the shared building blocks every widget ui.tsx composes.
 * Controls here enforce the station rules (control lock, edit mode,
 * pending writes) so individual widgets never re-implement them.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useBypass, useCanOperate, useChannel, useCommand, useNow, useStation } from "../lib/hooks";
import { useFrame } from "../lib/frame";
import { ago, fmtValue, toneOf } from "../lib/format";
import type { ChannelInfo, DeviceInfo, Tone } from "../lib/types";

export { expandBinds, useBypass, useCanOperate, useChannel, useCommand, useDevice, useStation, useNow, useTopic, useViewState } from "../lib/hooks";
export { useFrame } from "../lib/frame";
export * from "../lib/format";
export type { WidgetProps } from "../lib/types";

const cx = (...c: (string | number | false | undefined | null)[]) => c.filter(Boolean).join(" ");

// ------------------------------------------------------------------ text
export function Title({ children, sub, right }: { children: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="w-title">
      <div className="w-title-main">
        <span className="w-title-text">{children}</span>
        {sub && <span className="w-title-sub">{sub}</span>}
      </div>
      {right}
    </div>
  );
}

export function Unbound({ what = "a channel" }: { what?: string }) {
  return <div className="w-unbound">Not bound. Edit the layout and pick {what}.</div>;
}

/** A formatted live value, colored by limits/state. */
export function Value({ ch, className, precision, unit = true }: {
  ch?: string; className?: string; precision?: number; unit?: boolean;
}) {
  const { value, info } = useChannel(ch);
  return <Readout value={value} info={info} className={className} precision={precision} unit={unit} />;
}

export function Readout({ value, info, className, precision, unit = true }: {
  value: unknown; info?: ChannelInfo; className?: string; precision?: number; unit?: boolean;
}) {
  const tone = toneOf(value, info);
  return (
    <span className={cx("readout", tone && `tone-${tone}`, className)}>
      <span className="readout-num">{fmtValue(value, info, precision)}</span>
      {unit && info?.unit && value !== null && value !== undefined && <span className="readout-unit">{info.unit}</span>}
    </span>
  );
}

export function Led({ on, tone, size = 12 }: { on: boolean; tone?: Tone; size?: number }) {
  return <span className={cx("led", on && "on", tone && `tone-${tone}`)} style={{ width: size, height: size }} />;
}

export function Chip({ tone, children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span key={String(children)} className={cx("chip", tone && `tone-${tone}`, "flash", className)}>{children}</span>;
}

/** Chip showing an enum/bool channel's state. */
export function StateChip({ ch, onText = "ON", offText = "OFF" }: { ch?: string; onText?: string; offText?: string }) {
  const { value, info } = useChannel(ch);
  const text = typeof value === "boolean" ? (value ? onText : offText) : fmtValue(value, info);
  return <Chip tone={toneOf(value, info)}>{text}</Chip>;
}

/** "set by Station 2 · 4 s ago" */
export function WriterNote({ ch }: { ch?: string }) {
  const st = useStation();
  const { writer } = useChannel(ch);
  useNow(1000);
  if (!writer) return null;
  return <div className="writer-note">{writer.by} · {ago(writer.ts, st.now())}</div>;
}

// ------------------------------------------------------------------ controls
function useWritable(ch?: string) {
  const snap = useChannel(ch);
  const op = useCanOperate();
  const can = op.ok && !!snap.info?.writable;
  const why = !snap.info ? "Unknown channel" : !snap.info.writable ? "Read-only" : op.reason;
  return { ...snap, can, why };
}

/** ON / OFF button for a writable boolean (valves, pumps, enables). */
export function OnOff({ ch, onText = "ON", offText = "OFF", wide }: {
  ch?: string; onText?: string; offText?: string; wide?: boolean;
}) {
  const st = useStation();
  const { value, pending, can, why, lock } = useWritable(ch);
  const bypass = useBypass();
  const on = value === true;
  const locked = !!lock;
  return (
    <button
      className={cx("onoff", on && "on", pending && "pending", wide && "wide")}
      disabled={!can || (locked && !bypass)}
      title={locked ? `Interlocked: ${lock}${bypass ? " (OVERRIDE active: click will bypass)" : ""}`
        : can ? `Switch ${on ? offText : onText}` : why}
      onClick={() => ch && st.write(ch, !on)}
    >
      {on ? onText : offText}
    </button>
  );
}

/** Interlock status for a channel: OK, LOCKED (reason on hover) or BYPASSED under override. */
export function LockChip({ ch }: { ch?: string }) {
  const { lock, info } = useChannel(ch);
  const bypass = useBypass();
  if (!info?.interlocked) return <span className="lock-chip-empty" />;
  if (!lock) return <Chip tone="ok" className="lock-chip">OK</Chip>;
  return (
    <span title={`Interlocked: ${lock}`}>
      <Chip tone={bypass ? "alarm" : "warn"} className="lock-chip">{bypass ? "BYPASSED" : "LOCKED"}</Chip>
    </span>
  );
}

export function LockIcon({ size = 10 }: { size?: number }) {
  return (
    <svg className="lock-icon" width={size} height={size} viewBox="0 0 16 16" aria-label="interlocked">
      <rect x="2.5" y="7" width="11" height="8" rx="1.5" fill="currentColor" />
      <path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

/** The live interlock reason for a channel, if it can't change right now. */
export function LockNote({ ch }: { ch?: string }) {
  const { lock } = useChannel(ch);
  if (!lock) return null;
  return <div className="lock-note" title={lock}><LockIcon size={9} /> {lock}</div>;
}

/** Numeric setpoint box. Shows the live value; type and press Enter to write. */
export function NumField({ ch, width = 76 }: { ch?: string; width?: number }) {
  const st = useStation();
  const { value, info, pending, can, why } = useWritable(ch);
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? (typeof value === "number" ? fmtValue(value, info) : "");
  const commit = () => {
    if (draft === null || !ch) return;
    const v = Number(draft);
    setDraft(null);
    if (draft.trim() !== "" && Number.isFinite(v) && v !== value) st.write(ch, v);
  };
  return (
    <span className="numfield">
      <input
        className={cx("num-input", pending && "pending", draft !== null && "dirty")}
        style={{ width }}
        value={shown}
        disabled={!can}
        title={can ? `${info?.label ?? ""}${info?.min !== undefined ? ` (${info.min} to ${info.max})` : ""}` : why}
        inputMode="decimal"
        onChange={(e) => setDraft(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") { setDraft(null); (e.target as HTMLInputElement).blur(); }
        }}
      />
      {info?.unit && <span className="num-unit">{info.unit}</span>}
    </span>
  );
}

export function SelectField({ ch }: { ch?: string }) {
  const st = useStation();
  const { value, info, pending, can, why } = useWritable(ch);
  return (
    <select className={cx("select", pending && "pending")} value={String(value ?? "")} disabled={!can}
      title={can ? info?.label : why} onChange={(e) => ch && st.write(ch, e.target.value)}>
      {info?.options?.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

/** Segmented selector for an enum channel. */
export function Segmented({ ch }: { ch?: string }) {
  const st = useStation();
  const { value, info, pending, can, why } = useWritable(ch);
  return (
    <div className={cx("segmented", pending && "pending")} title={can ? "" : why}>
      {info?.options?.map((o) => (
        <button key={o} className={cx(o === value && "sel", o === value && info.states?.[o] && `tone-${info.states[o]}`)}
          disabled={!can} onClick={() => ch && o !== value && st.write(ch, o)}>{o}</button>
      ))}
    </div>
  );
}

/**
 * Runs an engine command. Commands marked `danger` need a 0.8 s press-and-hold;
 * commands marked `confirm` need a second click within 3 s.
 */
export function CmdButton({ cmd, label, className, big }: { cmd?: string; label?: ReactNode; className?: string; big?: boolean }) {
  const st = useStation();
  const info = useCommand(cmd);
  const op = useCanOperate();
  const [busy, setBusy] = useState(false);
  const [arm, setArm] = useState(false);
  const [holding, setHolding] = useState(false);
  const timer = useRef<number>(0);
  useEffect(() => () => clearTimeout(timer.current), []);
  if (!info) return <button className="cmd" disabled title="Unknown command">{label ?? cmd ?? "—"}</button>;

  const run = async () => {
    setBusy(true);
    const ack = await st.command(info.name);
    setBusy(false);
    if (ack.ok) st.toast(`${info.label} done`, "ok");
  };
  const can = op.ok && !busy;
  const text = label ?? info.label;
  const hold = {
    onPointerDown: () => {
      if (!can) return;
      setHolding(true);
      timer.current = window.setTimeout(() => { setHolding(false); run(); }, 800);
    },
    onPointerUp: () => { clearTimeout(timer.current); setHolding(false); },
    onPointerLeave: () => { clearTimeout(timer.current); setHolding(false); },
  };
  const click = () => {
    if (!can) return;
    if (!info.confirm) return run();
    if (arm) { setArm(false); clearTimeout(timer.current); run(); }
    else { setArm(true); timer.current = window.setTimeout(() => setArm(false), 3000); }
  };
  return (
    <button
      className={cx("cmd", info.danger && "danger", busy && "pending", holding && "holding", arm && "armed", big && "big", className)}
      disabled={!can}
      title={op.ok ? info.description || (info.danger ? "Press and hold" : info.label) : op.reason}
      {...(info.danger ? hold : { onClick: click })}
    >
      <span className="cmd-fill" />
      <span className="cmd-text">{arm ? "Confirm?" : holding ? "Hold…" : text}</span>
    </button>
  );
}

// ------------------------------------------------------------------ rows
export function Row({ label, children, title, note, lock }: {
  label: ReactNode; children: ReactNode; title?: string; note?: ReactNode; lock?: ReactNode;
}) {
  return (
    <div className="row" title={title}>
      <span className="row-label">{label}{note}</span>
      {lock !== undefined && <span className="row-lock">{lock}</span>}
      <span className="row-value">{children}</span>
    </div>
  );
}

/** Renders any channel as a row, picking the right control for its type.
 *  `lockColumn` adds the interlock status column (OK / LOCKED / BYPASSED). */
export function ChannelRow({ ch, label, lockColumn }: { ch: string; label?: ReactNode; lockColumn?: boolean }) {
  const { info } = useChannel(ch);
  if (!info) return <Row label={label ?? ch}><span className="dim">missing</span></Row>;
  const lbl = label ?? info.label;
  let body: ReactNode;
  if (info.kind === "bool") {
    body = info.writable ? <OnOff ch={ch} /> : <StateChip ch={ch} />;
  } else if (info.kind === "enum") {
    body = info.writable ? <SelectField ch={ch} /> : <StateChip ch={ch} />;
  } else if (info.kind === "number" && info.writable) {
    body = <NumField ch={ch} />;
  } else {
    body = <Value ch={ch} />;
  }
  return (
    <Row label={lbl} title={info.description || info.name} note={<LockNote ch={ch} />}
      lock={lockColumn ? <LockChip ch={ch} /> : undefined}>{body}</Row>
  );
}

/** A row for one role of a device, e.g. <RoleRow dev={dev} role="rpm" label="Speed" />. */
export function RoleRow({ dev, role, label, lockColumn }: { dev: DeviceInfo; role: string; label?: ReactNode; lockColumn?: boolean }) {
  const ch = dev.channels[role];
  if (!ch) return null;
  return <ChannelRow ch={ch} label={label} lockColumn={lockColumn} />;
}

// ------------------------------------------------------------------ trends
/** Small trend line from the station's shared history. */
export function Sparkline({ ch, seconds = 60, color = "var(--accent)", height = 36, log }: {
  ch?: string; seconds?: number; color?: string; height?: number; log?: boolean;
}) {
  const st = useStation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef({ v: -1, w: 0 });
  useFrame(() => {
    const c = canvas.current;
    if (!c || !ch) return;
    const w = c.clientWidth;
    if (st.history.version === last.current.v && w === last.current.w) return;
    last.current = { v: st.history.version, w };
    const dpr = window.devicePixelRatio || 1;
    c.width = w * dpr;
    c.height = height * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    const now = st.now();
    const { t, v } = st.history.slice([ch], now - seconds);
    const ys = v[0].map((y) => (y === null ? null : log ? Math.log10(Math.max(y, 1e-12)) : y));
    const finite = ys.filter((y): y is number => y !== null);
    if (finite.length < 2) return;
    let lo = Math.min(...finite), hi = Math.max(...finite);
    if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.12;
    lo -= pad; hi += pad;
    const X = (ts: number) => ((ts - (now - seconds)) / seconds) * w;
    const Y = (y: number) => height - ((y - lo) / (hi - lo)) * height;
    const col = getComputedStyle(c).getPropertyValue("--spark").trim() || color;
    g.beginPath();
    let started = false;
    ys.forEach((y, k) => {
      if (y === null) { started = false; return; }
      if (!started) { g.moveTo(X(t[k]), Y(y)); started = true; } else g.lineTo(X(t[k]), Y(y));
    });
    g.strokeStyle = col;
    g.lineWidth = 1.5;
    g.stroke();
    g.lineTo(X(t[t.length - 1]), height);
    g.lineTo(X(t[0]), height);
    g.closePath();
    const grad = g.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, col + "55");
    grad.addColorStop(1, col + "00");
    g.fillStyle = grad;
    g.fill();
  });
  return <canvas ref={canvas} className="sparkline" style={{ height, ["--spark" as any]: color }} />;
}

export { cx };
