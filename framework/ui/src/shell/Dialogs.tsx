import { useEffect, useMemo, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { useStation, useTopic } from "../lib/hooks";
import type { ChannelInfo, SettingSpec, WidgetItem, WidgetSpec } from "../lib/types";

export function Modal({ title, children, onClose, footer, wide }: {
  title: string; children: ReactNode; onClose: () => void; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className={cx("modal", wide && "wide")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head"><b>{title}</b><button className="iconbtn" onClick={onClose}>✕</button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ add widget
export function AddWidget({ specs, onPick, onClose }: {
  specs: WidgetSpec[]; onPick: (spec: WidgetSpec, device?: string) => void; onClose: () => void;
}) {
  const st = useStation();
  useTopic("catalog");
  const cats = ["Device", "Control", "General", "Trend"];
  return (
    <Modal title="Add widget" onClose={onClose} wide>
      {cats.map((cat) => {
        const list = specs.filter((s) => s.category === cat);
        if (!list.length) return null;
        return (
          <section key={cat} className="palette-sec">
            <h4>{cat === "Device" ? "Devices on this engine" : cat}</h4>
            <div className="palette">
              {list.map((s) => {
                if (s.bind === "device") {
                  const devs = [...st.devices.values()].filter((d) => d.type === s.type);
                  if (!devs.length) return null;
                  return devs.map((d) => (
                    <button key={d.id} className="pal-item" onClick={() => onPick(s, d.id)}>
                      <b>{d.label}</b><span>{s.label} · {d.id}</span>
                    </button>
                  ));
                }
                return (
                  <button key={s.type} className="pal-item" onClick={() => onPick(s)}>
                    <b>{s.label}</b><span>{s.description}</span>
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </Modal>
  );
}

// ------------------------------------------------------------------ inspector
function groupChannels(chs: ChannelInfo[]) {
  const g = new Map<string, ChannelInfo[]>();
  for (const c of chs) {
    const k = c.group || "other";
    if (!g.has(k)) g.set(k, []);
    g.get(k)!.push(c);
  }
  return [...g.entries()];
}

function ChannelSelect({ value, options, onChange }: { value?: string; options: ChannelInfo[]; onChange: (v: string) => void }) {
  return (
    <select className="select full" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      <option value="">— none —</option>
      {groupChannels(options).map(([g, list]) => (
        <optgroup key={g} label={g}>
          {list.map((c) => <option key={c.name} value={c.name}>{c.label} · {c.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function MultiPick({ items, selected, onChange }: {
  items: { id: string; label: string; group: string }[]; selected: string[]; onChange: (v: string[]) => void;
}) {
  const [q, setQ] = useState("");
  const shown = items.filter((i) => `${i.label} ${i.id}`.toLowerCase().includes(q.toLowerCase()));
  const pattern = q.includes("*") ? q.trim() : null;     // "rtd.*" binds every channel that matches, now and later
  const patterns = selected.filter((s) => s.includes("*") && s !== pattern);
  const groups = new Map<string, typeof items>();
  if (pattern || patterns.length) groups.set("patterns", [...(pattern ? [pattern] : []), ...patterns].map((p) => ({ id: p, label: "every channel matching", group: "patterns" })));
  shown.forEach((i) => { if (!groups.has(i.group)) groups.set(i.group, []); groups.get(i.group)!.push(i); });
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  return (
    <div className="multipick">
      <input className="num-input full" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="mp-list">
        {[...groups.entries()].map(([g, list]) => (
          <div key={g}>
            <div className="mp-group">{g || "other"}</div>
            {list.map((i) => (
              <label key={i.id} className="mp-item">
                <input type="checkbox" checked={selected.includes(i.id)} onChange={() => toggle(i.id)} />
                <span>{i.label}</span><span className="dim">{i.id}</span>
              </label>
            ))}
          </div>
        ))}
      </div>
      <div className="dim small">{selected.length} selected. Rows show in the order you pick them. Type a pattern such as <code>rtd.*</code> to bind a whole group.</div>
    </div>
  );
}

export function Inspector({ item, spec, onApply, onClose }: {
  item: WidgetItem; spec: WidgetSpec; onApply: (item: WidgetItem) => void; onClose: () => void;
}) {
  const st = useStation();
  useTopic("catalog");
  const [draft, setDraft] = useState<WidgetItem>(() => ({ ...item, options: { ...(item.options ?? {}) } }));
  const set = (patch: Partial<WidgetItem>) => setDraft((d) => ({ ...d, ...patch }));
  const setOpt = (k: string, v: unknown) => setDraft((d) => ({ ...d, options: { ...d.options, [k]: v } }));

  const channels = useMemo(() => [...st.channels.values()].filter((c) =>
    (!spec.accepts.length || spec.accepts.includes(c.kind)) && (!spec.writable_only || c.writable)), [st.channels, spec]);
  const allNumbers = useMemo(() => [...st.channels.values()].filter((c) => c.kind === "number"), [st.channels]);
  const commands = [...st.commands.values()];

  const field = (s: SettingSpec) => {
    const v = draft.options?.[s.key] ?? s.default;
    switch (s.kind) {
      case "bool":
        return <input type="checkbox" checked={!!v} onChange={(e) => setOpt(s.key, e.target.checked)} />;
      case "number":
        return <input className="num-input" type="number" value={v === undefined || v === null ? "" : String(v)}
          onChange={(e) => setOpt(s.key, e.target.value === "" ? undefined : Number(e.target.value))} />;
      case "select":
        return <select className="select" value={String(v)} onChange={(e) => setOpt(s.key, e.target.value)}>
          {s.options?.map((o) => <option key={o}>{o}</option>)}</select>;
      case "textarea":
        return <textarea className="textarea" rows={6} value={String(v ?? "")} onChange={(e) => setOpt(s.key, e.target.value)} />;
      case "channel":
        return <ChannelSelect value={v as string} options={allNumbers} onChange={(x) => setOpt(s.key, x || undefined)} />;
      case "diagram":
        return <select className="select full" value={String(v ?? "")} onChange={(e) => setOpt(s.key, e.target.value || undefined)}>
          <option value="">— choose —</option>
          {[...st.diagrams.values()].map((d) => <option key={d.id} value={d.id}>{d.title} · {d.id}</option>)}
        </select>;
      case "commands":
        return <MultiPick items={commands.map((c) => ({ id: c.name, label: c.label, group: c.group }))}
          selected={(v as string[]) ?? []} onChange={(x) => setOpt(s.key, x)} />;
      default:
        return <input className="num-input full" value={String(v ?? "")} onChange={(e) => setOpt(s.key, e.target.value)} />;
    }
  };

  return (
    <Modal title={`${spec.label} settings`} onClose={onClose}
      footer={<><button className="hbtn" onClick={onClose}>Cancel</button>
        <button className="hbtn primary" onClick={() => onApply(draft)}>Apply</button></>}>
      <div className="form">
        <label>Title<input className="num-input full" placeholder="(automatic)" value={draft.title ?? ""}
          onChange={(e) => set({ title: e.target.value || undefined })} /></label>
        {spec.bind === "channel" && (
          <label>Channel<ChannelSelect value={draft.bind} options={channels} onChange={(v) => set({ bind: v || undefined })} /></label>
        )}
        {spec.bind === "channels" && (
          <label>Channels<MultiPick items={channels.map((c) => ({ id: c.name, label: c.label, group: c.group }))}
            selected={draft.binds ?? []} onChange={(v) => set({ binds: v })} /></label>
        )}
        {spec.bind === "command" && (
          <label>Command
            <select className="select full" value={draft.command ?? ""} onChange={(e) => set({ command: e.target.value || undefined })}>
              <option value="">— none —</option>
              {commands.map((c) => <option key={c.name} value={c.name}>{c.label} · {c.name}</option>)}
            </select>
          </label>
        )}
        {spec.bind === "device" && (
          <label>Device
            <select className="select full" value={draft.device ?? ""} onChange={(e) => set({ device: e.target.value || undefined })}>
              {[...st.devices.values()].filter((d) => d.type === spec.type).map((d) =>
                <option key={d.id} value={d.id}>{d.label} · {d.id}</option>)}
            </select>
          </label>
        )}
        {spec.settings.map((s) => <label key={s.key}>{s.label}{field(s)}</label>)}
      </div>
    </Modal>
  );
}

export function OverrideConfirm({ onClose }: { onClose: () => void }) {
  const st = useStation();
  return (
    <Modal title="Override interlocks?" onClose={onClose}
      footer={<><button className="hbtn" onClick={onClose}>Cancel</button>
        <button className="hbtn danger" onClick={() => { st.setOverride(true); onClose(); }}>Override interlocks</button></>}>
      <p>
        While the override is on, this station can operate valves, pumps and outputs even when an interlock
        would block them. Locked controls stay marked so you can see what you are bypassing.
      </p>
      <p style={{ marginTop: 10 }}>
        Every station sees the override, an alarm stays raised, and each bypassed interlock is logged.
        It ends when you click End override, release control, or lose control. Device self-protection
        (trips, dropped permits) still acts.
      </p>
    </Modal>
  );
}

export function TakeControl({ holder, onClose }: { holder: string; onClose: () => void }) {
  const st = useStation();
  return (
    <Modal title="Take control?" onClose={onClose}
      footer={<><button className="hbtn" onClick={onClose}>Cancel</button>
        <button className="hbtn danger" onClick={() => { st.claim(true); onClose(); }}>Take control from {holder}</button></>}>
      <p>{holder} is operating. Taking control makes their station view-only immediately, and the event log records the takeover.</p>
    </Modal>
  );
}
