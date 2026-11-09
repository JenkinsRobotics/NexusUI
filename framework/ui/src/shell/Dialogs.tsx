import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { useStation, useTopic } from "../lib/hooks";
import type { ChannelInfo, SettingSpec, WidgetItem, WidgetSpec } from "../lib/types";
import { sizeFor, widgetUIs } from "./registry";
import { Boundary } from "./WidgetFrame";

export function Modal({ title, children, onClose, footer, wide, editor }: {
  title: string; children: ReactNode; onClose: () => void; footer?: ReactNode; wide?: boolean; editor?: boolean;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className={cx("modal", wide && "wide", editor && "editor")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head"><b>{title}</b><button className="iconbtn" onClick={onClose}>✕</button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ I/O classes
/** How the editor files a channel: on/off outputs and inputs, values you set or read, states, text. */
export function ioClass(c: ChannelInfo): string {
  if (c.kind === "bool") return c.writable ? "DO" : "DI";
  if (c.kind === "number") return c.writable ? "AO" : "AI";
  if (c.kind === "enum") return "STATE";
  return "TEXT";
}
const IO_NAMES: Record<string, string> = {
  DO: "Digital out", DI: "Digital in", AO: "Analog out", AI: "Analog in", STATE: "States", TEXT: "Text", FN: "Functions",
};
const IO_ORDER = ["DO", "DI", "AO", "AI", "STATE", "TEXT", "FN"];

interface PickItem { id: string; label: string; sub: string; group: string; cls: string }
const chanItem = (c: ChannelInfo): PickItem => ({ id: c.name, label: c.label, sub: c.name + (c.unit ? ` · ${c.unit}` : ""), group: c.group || "other", cls: ioClass(c) });

/**
 * Chooses channels or functions. Filter chips by I/O class, a search box, and the rows
 * grouped by their source (device or group prefix). Single or multiple selection; a
 * search containing * can be added as a pattern that follows every matching channel.
 */
function Picker({ items, selected, onChange, multi, patterns = multi }: {
  items: PickItem[]; selected: string[]; onChange: (v: string[]) => void; multi: boolean; patterns?: boolean;
}) {
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const classes = IO_ORDER.filter((k) => items.some((i) => i.cls === k));
  const shown = items.filter((i) => (!cls || i.cls === cls) && `${i.label} ${i.id}`.toLowerCase().includes(q.toLowerCase()));
  const pattern = patterns && q.includes("*") ? q.trim() : null;
  const chosenPatterns = selected.filter((x) => x.includes("*") && x !== pattern);
  const groups = new Map<string, PickItem[]>();
  for (const i of shown) { if (!groups.has(i.group)) groups.set(i.group, []); groups.get(i.group)!.push(i); }
  const pick = (id: string) => {
    if (!multi) return onChange(selected[0] === id ? [] : [id]);
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };
  const flip = (g: string) => setClosed((c) => { const n = new Set(c); n.has(g) ? n.delete(g) : n.add(g); return n; });
  return (
    <div className="picker">
      <div className="pk-tools">
        <input className="num-input full" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {classes.length > 1 && (
        <div className="pk-chips">
          <button className={cx("chipbtn", !cls && "sel")} onClick={() => setCls("")}>All</button>
          {classes.map((k) => (
            <button key={k} className={cx("chipbtn", cls === k && "sel")} title={IO_NAMES[k]} onClick={() => setCls(cls === k ? "" : k)}>
              {k === "STATE" || k === "TEXT" || k === "FN" ? IO_NAMES[k] : k}
              <span className="pk-n">{items.filter((i) => i.cls === k).length}</span>
            </button>
          ))}
        </div>
      )}
      <div className="pk-list">
        {(pattern || chosenPatterns.length > 0) && (
          <div className="pk-group">
            <div className="pk-ghead">patterns</div>
            {[...(pattern ? [pattern] : []), ...chosenPatterns].map((pt) => (
              <label key={pt} className={cx("pk-row", selected.includes(pt) && "on")}>
                <input type="checkbox" checked={selected.includes(pt)} onChange={() => pick(pt)} />
                <span className="pk-label">every channel matching</span><span className="pk-tag">*</span><span className="pk-sub">{pt}</span>
              </label>
            ))}
          </div>
        )}
        {[...groups.entries()].map(([g, list]) => (
          <div key={g} className="pk-group">
            <button className="pk-ghead" onClick={() => flip(g)}>
              <span className="pk-arrow">{closed.has(g) ? "▸" : "▾"}</span>{g}<span className="pk-n">{list.length}</span>
            </button>
            {!closed.has(g) && list.map((i) => (
              <label key={i.id} className={cx("pk-row", selected.includes(i.id) && "on")}>
                <input type={multi ? "checkbox" : "radio"} checked={selected.includes(i.id)} onChange={() => pick(i.id)} />
                <span className="pk-label">{i.label}</span>
                <span className={cx("pk-tag", `io-${i.cls}`)}>{i.cls}</span>
                <span className="pk-sub">{i.sub}</span>
              </label>
            ))}
          </div>
        ))}
        {!shown.length && !pattern && <div className="dim small" style={{ padding: 8 }}>Nothing matches.</div>}
      </div>
      <div className="dim small">
        {multi ? `${selected.length} selected, shown in the order picked.` : selected[0] ?? "Nothing selected."}
        {patterns && " Type a pattern such as rtd.* to follow a whole group."}
      </div>
    </div>
  );
}

function ChannelSelect({ value, options, onChange }: { value?: string; options: ChannelInfo[]; onChange: (v: string) => void }) {
  const groups = new Map<string, ChannelInfo[]>();
  for (const c of options) { const k = c.group || "other"; if (!groups.has(k)) groups.set(k, []); groups.get(k)!.push(c); }
  return (
    <select className="select full" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      <option value="">— none —</option>
      {[...groups.entries()].map(([g, list]) => (
        <optgroup key={g} label={g}>
          {list.map((c) => <option key={c.name} value={c.name}>{c.label} · {c.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

// ------------------------------------------------------------------ widget editor
// Grid geometry for the preview: the same cell maths as the station grid at a typical width.
const COL_PX = 45, ROW_PX = 10, GAP = 8;
const previewPx = (w: number, h: number) => ({ width: w * COL_PX + (w - 1) * GAP, height: h * ROW_PX + (h - 1) * GAP });
const SIZE_NAMES: Record<string, string> = { s: "Small", m: "Medium", l: "Large", t: "Tall", xl: "Wide" };
const CATS = ["Control", "General", "Trend"];

/**
 * One dialog for adding and for editing a widget: the catalogue on the left (widgets and
 * the devices on this engine), a live preview in the middle, settings on the right.
 */
export function WidgetEditor({ specs, item, onApply, onClose }: {
  specs: Record<string, WidgetSpec>;
  item?: WidgetItem;                       // the widget being edited; omit to add a new one
  onApply: (item: WidgetItem) => void;
  onClose: () => void;
}) {
  const st = useStation();
  useTopic("catalog");
  const adding = !item;
  const [tab, setTab] = useState<"widgets" | "devices">(item?.device ? "devices" : "widgets");
  const [draft, setDraft] = useState<WidgetItem>(() =>
    item ? { ...item, options: { ...(item.options ?? {}) } } : { i: "", type: "", x: 0, y: 0, w: 8, h: 10 });
  const spec = specs[draft.type];
  const set = (patch: Partial<WidgetItem>) => setDraft((d) => ({ ...d, ...patch }));
  const setOpt = (k: string, v: unknown) => setDraft((d) => ({ ...d, options: { ...d.options, [k]: v } }));

  const choose = (s: WidgetSpec, device?: string) => setDraft((d) => {
    const size = d.type === s.type && d.size ? d.size : s.default_size;
    const [w, h] = s.size_cells[size] ?? [d.w, d.h];
    const same = d.type === s.type;
    return {
      ...d, type: s.type, size, w, h, device,
      options: same ? d.options : {},
      bind: same || (s.bind === "channel" && specs[d.type]?.bind === "channel") ? d.bind : undefined,
      binds: same || (s.bind === "channels" && specs[d.type]?.bind === "channels") ? d.binds : undefined,
      command: same || s.bind === "command" ? d.command : undefined,
    };
  });
  const resize = (size: string) => { const c = spec?.size_cells[size]; if (c) set({ size, w: c[0], h: c[1] }); };

  const channels = useMemo(() => [...st.channels.values()].filter((c) =>
    !spec || ((!spec.accepts.length || spec.accepts.includes(c.kind)) && (!spec.writable_only || c.writable))), [st.channels, spec]);
  const allNumbers = useMemo(() => [...st.channels.values()].filter((c) => c.kind === "number"), [st.channels]);
  const commands = [...st.commands.values()];
  const fnItems: PickItem[] = commands.map((c) => ({ id: c.name, label: c.label, sub: c.name, group: c.group || "other", cls: "FN" }));
  const devices = [...st.devices.values()].filter((d) => specs[d.type]);

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
        return <Picker items={fnItems} selected={(v as string[]) ?? []} onChange={(x) => setOpt(s.key, x)} multi patterns={false} />;
      default:
        return <input className="num-input full" value={String(v ?? "")} onChange={(e) => setOpt(s.key, e.target.value)} />;
    }
  };

  const Comp = spec ? widgetUIs[draft.type] : undefined;
  const size = draft.size && spec?.size_cells[draft.size] ? draft.size : sizeFor(spec, draft.w, draft.h);
  const box = previewPx(draft.w, draft.h);

  // the preview is drawn at grid size and scaled down when the stage is smaller
  const stage = useRef<HTMLDivElement>(null);
  const [stageBox, setStageBox] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setStageBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [spec]);
  const scale = stageBox.w ? Math.min(1, (stageBox.w - 40) / box.width, (stageBox.h - 40) / box.height) : 1;
  useEffect(() => {     // bring what is already chosen into view
    document.querySelector(".we-item.sel")?.scrollIntoView({ block: "center" });
    document.querySelector(".pk-row.on")?.scrollIntoView({ block: "nearest" });
  }, []);

  return (
    <Modal title={adding ? "Add widget" : `Edit ${spec?.label ?? "widget"}`} onClose={onClose} editor
      footer={<>
        <span className="dim small grow">{spec ? `${spec.label} · ${draft.w}×${draft.h} cells` : "Pick a widget or a device on the left."}</span>
        <button className="hbtn" onClick={onClose}>Cancel</button>
        <button className="hbtn primary" disabled={!spec} onClick={() => onApply(draft)}>{adding ? "Add widget" : "Apply"}</button>
      </>}>
      <div className="we">
        <aside className="we-left">
          <div className="we-tabs">
            <button className={cx("chipbtn", tab === "widgets" && "sel")} onClick={() => setTab("widgets")}>Widgets</button>
            <button className={cx("chipbtn", tab === "devices" && "sel")} onClick={() => setTab("devices")}>Devices <span className="pk-n">{devices.length}</span></button>
          </div>
          <div className="we-list">
            {tab === "widgets" && CATS.map((cat) => {
              const list = Object.values(specs).filter((s) => s.category === cat);
              if (!list.length) return null;
              return (
                <div key={cat} className="pk-group">
                  <div className="pk-ghead">{cat}</div>
                  {list.map((s) => (
                    <button key={s.type} className={cx("we-item", !draft.device && draft.type === s.type && "sel")} onClick={() => choose(s)} title={s.description}>
                      <b>{s.label}</b><span>{s.description}</span>
                    </button>
                  ))}
                </div>
              );
            })}
            {tab === "devices" && (devices.length ? (
              <div className="pk-group">
                <div className="pk-ghead">on this engine</div>
                {devices.map((d) => (
                  <button key={d.id} className={cx("we-item", draft.device === d.id && "sel")} onClick={() => choose(specs[d.type], d.id)}>
                    <b>{d.label}</b><span>{specs[d.type].label} · {d.id}</span>
                  </button>
                ))}
              </div>
            ) : <div className="dim small" style={{ padding: 10 }}>This app declares no devices. Device cards appear here when the app creates one, such as <code>Motor(eng, "m1")</code>.</div>)}
          </div>
        </aside>

        <section className="we-center">
          {spec ? (
            <>
              <div className="we-sizes">
                {spec.sizes.map((sz) => (
                  <button key={sz} className={cx("chipbtn", sz === size && "sel")} onClick={() => resize(sz)}>{SIZE_NAMES[sz] ?? sz}</button>
                ))}
              </div>
              <div className="we-stage" ref={stage}>
                <div style={{ width: box.width * scale, height: box.height * scale }}>
                  <div className={cx("wf", `wt-${draft.type}`, `ws-${size}`)} style={{ ...box, transform: scale < 1 ? `scale(${scale})` : undefined }}>
                    <div className="wf-content">
                      {Comp && <Boundary name={spec.label}><Comp item={draft} spec={spec} size={size} cells={{ w: draft.w, h: draft.h }} /></Boundary>}
                    </div>
                  </div>
                </div>
              </div>
              <div className="dim small we-hint">Live preview with the engine's current values{scale < 1 ? `, shown at ${Math.round(scale * 100)} %` : ""}. Controls are inactive here.</div>
            </>
          ) : (
            <div className="we-empty">
              <b>Choose what to add</b>
              <span>Widgets show or control the channels and functions your app declares. Devices are the premade cards for the devices the app created.</span>
            </div>
          )}
        </section>

        <aside className="we-right">
          {spec ? (
            <div className="form">
              <label>Title<input className="num-input full" placeholder="(automatic)" value={draft.title ?? ""}
                onChange={(e) => set({ title: e.target.value || undefined })} /></label>
              {spec.bind === "channel" && (
                <label>Channel<Picker items={channels.map(chanItem)} selected={draft.bind ? [draft.bind] : []}
                  onChange={(v) => set({ bind: v[0] })} multi={false} /></label>
              )}
              {spec.bind === "channels" && (
                <label>Channels<Picker items={channels.map(chanItem)} selected={draft.binds ?? []}
                  onChange={(v) => set({ binds: v })} multi /></label>
              )}
              {spec.bind === "command" && (
                <label>Function<Picker items={fnItems} selected={draft.command ? [draft.command] : []}
                  onChange={(v) => set({ command: v[0] })} multi={false} /></label>
              )}
              {spec.bind === "device" && (
                <label>Device
                  <select className="select full" value={draft.device ?? ""} onChange={(e) => set({ device: e.target.value || undefined })}>
                    {devices.filter((d) => d.type === spec.type).map((d) => <option key={d.id} value={d.id}>{d.label} · {d.id}</option>)}
                  </select>
                </label>
              )}
              {spec.settings.map((s) => <label key={s.key}>{s.label}{field(s)}</label>)}
            </div>
          ) : <div className="dim small" style={{ padding: 10 }}>Settings appear here once a widget is chosen.</div>}
        </aside>
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
