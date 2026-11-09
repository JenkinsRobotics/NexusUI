import { useState } from "react";
import { ls } from "../lib/ls";
import { clock, cx } from "../kit";
import { useNow, useStation, useTopic } from "../lib/hooks";
import type { Tab } from "../lib/types";

// ------------------------------------------------------------------ control
export function ControlBadge({ onTakeFrom }: { onTakeFrom: (holder: string) => void }) {
  const st = useStation();
  useTopic("control");
  useTopic("conn");
  if (st.status !== "open") return <span className="ctl ctl-off">OFFLINE</span>;
  if (st.control.mode === "open") return <span className="ctl ctl-open" title="Any station may operate">OPEN CONTROL</span>;
  if (st.inControl) {
    return (
      <span className="ctl-group">
        <span className="ctl ctl-mine">● IN CONTROL</span>
        <button className="hbtn" onClick={() => st.release()}>Release</button>
      </span>
    );
  }
  const holder = st.control.holder_name;
  return (
    <span className="ctl-group">
      <span className="ctl ctl-view">VIEW ONLY{holder ? ` · ${holder} operating` : ""}</span>
      <button className="hbtn primary" onClick={() => (holder ? onTakeFrom(holder) : st.claim())}>Take control</button>
    </span>
  );
}

export function OverrideControl({ onAsk }: { onAsk: () => void }) {
  const st = useStation();
  useTopic("control");
  useTopic("conn");
  const c = st.control;
  if (st.status !== "open") return null;
  if (c.override) {
    return (
      <span className="ctl-group">
        <span className="ctl ctl-override" title="Interlocks are not enforced">⚠ OVERRIDE{st.inControl ? "" : ` · ${c.override_by ?? ""}`}</span>
        {st.inControl && <button className="hbtn" onClick={() => st.setOverride(false)}>End override</button>}
      </span>
    );
  }
  if (!st.inControl) return null;
  return <button className="hbtn override-btn" onClick={onAsk} title="Bypass interlocks for manual control">Override</button>;
}

export function OverrideBanner() {
  const st = useStation();
  useTopic("control");
  if (!st.control.override) return null;
  return (
    <div className="override-banner">
      INTERLOCK OVERRIDE active ({st.control.override_by}). Interlocks are not enforced for the operating station.
      Device self-protection still acts. Every bypassed interlock is logged.
    </div>
  );
}

export function StationName() {
  const st = useStation();
  useTopic("stations");
  const [edit, setEdit] = useState<string | null>(null);
  const me = st.stations.find((s) => s.id === st.you?.id) ?? st.you;
  if (edit !== null) {
    return (
      <input className="name-input" autoFocus value={edit} maxLength={40}
        onChange={(e) => setEdit(e.target.value)}
        onBlur={() => { if (edit.trim()) st.rename(edit.trim()); setEdit(null); }}
        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEdit(null); }} />
    );
  }
  return <button className="station-name" title="This station's name (click to rename)" onClick={() => setEdit(me?.name ?? "")}>{me?.name ?? "…"}</button>;
}

// ------------------------------------------------------------------ tabs
export function TabBar({ tabs, active, editing, onSelect, onRename, onAdd, onRemove }: {
  tabs: Tab[]; active: string; editing: boolean;
  onSelect: (id: string) => void; onRename: (id: string, title: string) => void;
  onAdd: () => void; onRemove: (id: string) => void;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  return (
    <nav className="tabs">
      {tabs.map((t) => (
        <div key={t.id} className={cx("tab", t.id === active && "sel")}
          onClick={() => onSelect(t.id)} onDoubleClick={() => editing && setRenaming(t.id)}>
          {renaming === t.id ? (
            <input className="tab-input" autoFocus defaultValue={t.title}
              onBlur={(e) => { onRename(t.id, e.target.value.trim() || t.title); setRenaming(null); }}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
          ) : t.title}
          {editing && tabs.length > 1 && (
            <button className="tab-x" title="Delete tab" onClick={(e) => { e.stopPropagation(); onRemove(t.id); }}>✕</button>
          )}
        </div>
      ))}
      {editing && <button className="tab tab-add" onClick={onAdd} title="Add tab">+ Tab</button>}
    </nav>
  );
}

// ------------------------------------------------------------------ alerts sidebar
export function Sidebar() {
  const st = useStation();
  useTopic("alerts");
  useTopic("logs");
  const [view, setView] = useState<"alerts" | "events">("alerts");
  const [open, setOpenState] = useState(() => ls.get("vp.side") !== "hidden");
  const setOpen = (v: boolean) => { setOpenState(v); ls.set("vp.side", v ? "shown" : "hidden"); };
  const counts = { alarm: 0, warn: 0, info: 0 };
  for (const a of st.alerts) if (a.active || !a.acked) counts[a.level] = (counts[a.level] ?? 0) + 1;
  const unacked = st.alerts.filter((a) => !a.acked).length;

  if (!open) {
    return (
      <aside className="sidebar collapsed" onClick={() => setOpen(true)} title="Show alerts">
        <span className={cx("side-count", counts.alarm && "tone-alarm")}>{counts.alarm}</span>
        <span className={cx("side-count", counts.warn && "tone-warn")}>{counts.warn}</span>
        <span className="side-label">ALERTS</span>
      </aside>
    );
  }
  return (
    <aside className="sidebar">
      <div className="side-head">
        <span className="side-title">SYSTEM</span>
        <button className="iconbtn" title="Hide" onClick={() => setOpen(false)}>»</button>
      </div>
      <div className="side-counts">
        <span className={cx(counts.alarm && "tone-alarm")}>{counts.alarm} ALARM</span>
        <span className={cx(counts.warn && "tone-warn")}>{counts.warn} WARN</span>
        <span>{counts.info} INFO</span>
      </div>
      <div className="side-actions">
        <button className="hbtn" disabled={!unacked} onClick={() => st.ackAlerts("all")}>ACK ALL</button>
        <button className="hbtn" onClick={() => st.clearAlerts()} title="Remove cleared, acknowledged alerts">CLEAR OLD</button>
        <span className="grow" />
        <div className="seg-mini">
          <button className={cx(view === "alerts" && "sel")} onClick={() => setView("alerts")}>Alerts</button>
          <button className={cx(view === "events" && "sel")} onClick={() => setView("events")}>Events</button>
        </div>
      </div>
      <div className="side-list">
        {view === "alerts" ? (
          st.alerts.length === 0 ? <div className="dim small pad">No alerts.</div> :
          st.alerts.map((a) => (
            <div key={a.id} className={cx("alert", `lvl-${a.level}`, a.active && "active", !a.acked && "unacked")}
              onClick={() => !a.acked && st.ackAlerts([a.id])} title={a.acked ? "" : "Click to acknowledge"}>
              <div className="alert-head">
                <b>{a.level.toUpperCase()}</b>
                <span>{a.source}</span>
                {a.count > 1 && <span className="dim">×{a.count}</span>}
                <span className="grow" />
                <span className="dim">{a.active ? clock(a.ts) : "cleared"}</span>
              </div>
              <div className="alert-msg">{a.msg}</div>
            </div>
          ))
        ) : (
          [...st.logs].reverse().slice(0, 200).map((l, k) => (
            <div key={`${l.ts}-${k}`} className={cx("event", `lvl-${l.level}`)}>
              <span className="dim">{clock(l.ts)}</span> <span className="event-src">{l.source}</span> {l.msg}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}

// ------------------------------------------------------------------ status bar
export function StatusBar() {
  const st = useStation();
  useTopic("conn");
  useTopic("stats");
  useTopic("stations");
  useNow(1000);
  const ok = st.status === "open";
  const age = st.lastData ? (performance.now() - st.lastData) / 1000 : Infinity;
  return (
    <footer className="statusbar">
      <span className={cx("dot", ok ? "ok" : "bad")} />
      <span>{ok ? `Connected · ${st.engine?.name ?? ""}` : st.status === "connecting" ? "Connecting…" : "Disconnected, retrying"}</span>
      <span className="sb-item" title="Round trip to the engine">RTT {Number.isFinite(st.rtt) ? `${st.rtt.toFixed(1)} ms` : "—"}</span>
      <span className="sb-item" title="Messages received per second">{st.rate} msg/s</span>
      <span className={cx("sb-item", age > 2 && ok && "tone-warn")} title="Time since the last data update">
        data {Number.isFinite(age) ? (age < 1 ? "live" : `${age.toFixed(0)} s old`) : "—"}
      </span>
      <span className="grow" />
      <span className="sb-item" title={st.stations.map((s) => `${s.name} (${s.addr})`).join("\n")}>
        {st.stations.length} station{st.stations.length === 1 ? "" : "s"}: {st.stations.map((s) => s.name).join(", ")}
      </span>
      <span className="sb-item mono">{clock(st.now())}</span>
    </footer>
  );
}

export function Toasts() {
  const st = useStation();
  useTopic("toasts");
  return (
    <div className="toasts">
      {st.toasts.map((t) => <div key={t.id} className={cx("toast", `lvl-${t.level}`)}>{t.msg}</div>)}
    </div>
  );
}

export function ConnBanner() {
  const st = useStation();
  useTopic("conn");
  if (st.status === "open") return null;
  return <div className="conn-banner">Connection to the engine lost. Values are frozen and controls are disabled. Reconnecting…</div>;
}
