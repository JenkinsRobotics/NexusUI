import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cx } from "./kit";
import { EditCtx, useStation, useTopic } from "./lib/hooks";
import type { Layout, Tab, WidgetItem, WidgetSpec } from "./lib/types";
import { ConnBanner, ControlBadge, OverrideBanner, OverrideControl, Sidebar, StationName, StatusBar, TabBar, Toasts } from "./shell/Chrome";
import { AddWidget, Inspector, OverrideConfirm, TakeControl } from "./shell/Dialogs";
import { Grid, type GridConf } from "./shell/Grid";

const ls = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* blocked */ } },
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error ?? `${r.status} ${r.statusText}`);
  return body as T;
}

function normalize(l: Layout): Layout {
  const tabs = (l.tabs?.length ? l.tabs : [{ id: "main", title: "Main", widgets: [] }]).map((t, k) => ({
    id: t.id || `tab${k}`, title: t.title || `Tab ${k + 1}`,
    widgets: (t.widgets ?? []).map((w, j) => ({ ...w, i: w.i || `w${k}_${j}` })),
  }));
  return { ...l, version: 1, tabs };
}

const uid = () => Math.random().toString(36).slice(2, 9);

export default function App() {
  const st = useStation();
  useTopic("catalog");
  const layoutTopic = useTopic("layout");

  const [specs, setSpecs] = useState<Record<string, WidgetSpec>>({});
  const [grid, setGrid] = useState<GridConf>({ cols: 24, row_px: 10 });
  const [names, setNames] = useState<{ name: string; title: string }[]>([]);
  const [name, setName] = useState<string>(() => ls.get("vp.layout") ?? "");
  const [layout, setLayout] = useState<Layout | null>(null);
  const [active, setActive] = useState<string>(() => decodeURIComponent(location.hash.slice(1)) || ls.get("vp.tab") || "");
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [adding, setAdding] = useState(false);
  const [inspect, setInspect] = useState<WidgetItem | null>(null);
  const [takeFrom, setTakeFrom] = useState<string | null>(null);
  const [askOverride, setAskOverride] = useState(false);
  const [saveAs, setSaveAs] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const editingRef = useRef(editing);
  editingRef.current = editing;

  // ---- load specs + layout list
  const refreshNames = useCallback(async () => {
    const r = await api<{ layouts: { name: string; title: string }[]; default: string }>("/api/layouts");
    setNames(r.layouts);
    return r;
  }, []);

  const load = useCallback(async (n: string) => {
    try {
      const l = normalize(await api<Layout>(`/api/layouts/${encodeURIComponent(n)}`));
      setLayout(l);
      setName(n);
      setDirty(false);
      ls.set("vp.layout", n);
      setActive((a) => (l.tabs.some((t) => t.id === a) ? a : l.tabs[0].id));
      setError(null);
    } catch (e) {
      setError(`Could not load layout "${n}": ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const w = await api<{ widgets: WidgetSpec[]; grid: GridConf }>("/api/widgets");
        setSpecs(Object.fromEntries(w.widgets.map((s) => [s.type, s])));
        setGrid(w.grid);
        const r = await refreshNames();
        const want = name && r.layouts.some((l) => l.name === name) ? name : r.default;
        await load(want);
      } catch (e) {
        setError(`Cannot reach the engine API: ${(e as Error).message}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- another station saved a layout
  useEffect(() => {
    const ev = st.layoutEvent;
    if (!ev || ev.station === st.you?.id) return;
    refreshNames();
    if (ev.name !== name) return;
    if (editingRef.current) st.toast(`${ev.by ?? "Another station"} saved "${ev.name}" while you are editing. Saving will overwrite it.`, "warn");
    else if (!ev.deleted) { load(name); st.toast(`Layout updated by ${ev.by ?? "another station"}`, "info"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutTopic]);

  useEffect(() => {
    if (!active) return;
    ls.set("vp.tab", active);
    if (location.hash.slice(1) !== active) history.replaceState(null, "", `#${encodeURIComponent(active)}`);
  }, [active]);

  // keyboard: 1..9 switch tabs, E toggles edit
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input,textarea,select")) return;
      if (/^[1-9]$/.test(e.key) && layout) {
        const t = layout.tabs[Number(e.key) - 1];
        if (t) setActive(t.id);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [layout]);

  const tab: Tab | undefined = useMemo(() => layout?.tabs.find((t) => t.id === active) ?? layout?.tabs[0], [layout, active]);

  const updateTab = (fn: (t: Tab) => Tab, markDirty = true) => {
    setLayout((l) => (l ? { ...l, tabs: l.tabs.map((t) => (t.id === tab?.id ? fn(t) : t)) } : l));
    if (markDirty) setDirty(true);
  };

  const save = async (target = name) => {
    if (!layout) return;
    try {
      await api(`/api/layouts/${encodeURIComponent(target)}`, {
        method: "PUT",
        headers: { "content-type": "application/json", "x-station-name": st.you?.name ?? "", "x-station-id": st.you?.id ?? "" },
        body: JSON.stringify(layout),
      });
      setName(target);
      ls.set("vp.layout", target);
      setDirty(false);
      setEditing(false);
      await refreshNames();
      st.toast(`Saved layout "${target}"`, "ok");
    } catch (e) {
      st.toast(`Save failed: ${(e as Error).message}`, "alarm");
    }
  };

  const discard = async () => {
    setEditing(false);
    await load(name);
  };

  const addWidget = (spec: WidgetSpec, device?: string) => {
    if (!tab) return;
    const [w, h] = spec.size_cells[spec.default_size] ?? [8, 10];
    const item: WidgetItem = { i: `w${uid()}`, type: spec.type, x: 0, y: 10_000, w, h, size: spec.default_size, device };
    updateTab((t) => ({ ...t, widgets: [...t.widgets, item] }));
    setAdding(false);
    if (!device && spec.bind !== "none") setInspect(item);
  };

  if (error && !layout) return <div className="fatal">{error}</div>;

  return (
    <EditCtx.Provider value={editing}>
      <div className={cx("app", st.status !== "open" && "stale", editing && "is-editing")}>
        <header className="header">
          <div className="brand">
            <span className="brand-mark" />
            <span className="brand-name">{st.engine?.name ?? "NexusUI"}</span>
            <select className="select layout-pick" value={name} title="Layout"
              onChange={(e) => (dirty && !confirm("Discard unsaved layout changes?") ? null : load(e.target.value))}>
              {names.length === 0 && <option value={name}>{name || "default"}</option>}
              {names.map((n) => <option key={n.name} value={n.name}>{n.title} ({n.name})</option>)}
            </select>
          </div>
          {layout && tab && (
            <TabBar tabs={layout.tabs} active={tab.id} editing={editing} onSelect={setActive}
              onRename={(id, title) => { setLayout({ ...layout, tabs: layout.tabs.map((t) => (t.id === id ? { ...t, title } : t)) }); setDirty(true); }}
              onAdd={() => { const id = `tab${uid()}`; setLayout({ ...layout, tabs: [...layout.tabs, { id, title: "New tab", widgets: [] }] }); setActive(id); setDirty(true); }}
              onRemove={(id) => {
                if (!confirm("Delete this tab and its widgets?")) return;
                const tabs = layout.tabs.filter((t) => t.id !== id);
                setLayout({ ...layout, tabs });
                setActive(tabs[0].id);
                setDirty(true);
              }} />
          )}
          <div className="header-right">
            {editing ? (
              <>
                <button className="hbtn" onClick={() => setAdding(true)}>+ Widget</button>
                {saveAs !== null ? (
                  <input className="name-input" autoFocus placeholder="new-layout-name" value={saveAs}
                    onChange={(e) => setSaveAs(e.target.value.replace(/[^A-Za-z0-9_-]/g, ""))}
                    onBlur={() => setSaveAs(null)}
                    onKeyDown={(e) => { if (e.key === "Enter" && saveAs) { save(saveAs); setSaveAs(null); } if (e.key === "Escape") setSaveAs(null); }} />
                ) : (
                  <button className="hbtn" onClick={() => setSaveAs("")}>Save as…</button>
                )}
                <button className="hbtn" onClick={discard}>{dirty ? "Discard" : "Done"}</button>
                <button className="hbtn primary" disabled={!dirty} onClick={() => save()}>Save</button>
              </>
            ) : (
              <>
                <button className="hbtn" onClick={() => setEditing(true)} title="Rearrange, resize and add widgets">Edit layout</button>
                <ControlBadge onTakeFrom={setTakeFrom} />
                <OverrideControl onAsk={() => setAskOverride(true)} />
              </>
            )}
            <StationName />
          </div>
        </header>
        <ConnBanner />
        <OverrideBanner />
        {editing && <div className="edit-banner">Editing layout. Drag cards to move, drag any edge to resize, use the size buttons for presets. Controls are disabled while editing.</div>}
        <div className="body">
          <main className="main">
            {layout && tab && Object.keys(specs).length > 0 && (
              <Grid
                key={tab.id}
                tab={tab}
                specs={specs}
                grid={grid}
                editing={editing}
                onLayout={(widgets) => updateTab((t) => ({ ...t, widgets }), false)}
                onUserChange={() => setDirty(true)}
                onEdit={setInspect}
                onRemove={(it) => updateTab((t) => ({ ...t, widgets: t.widgets.filter((w) => w.i !== it.i) }))}
              />
            )}
          </main>
          <Sidebar />
        </div>
        <StatusBar />
        <Toasts />
        {adding && <AddWidget specs={Object.values(specs)} onPick={addWidget} onClose={() => setAdding(false)} />}
        {inspect && specs[inspect.type] && (
          <Inspector item={inspect} spec={specs[inspect.type]} onClose={() => setInspect(null)}
            onApply={(it) => { updateTab((t) => ({ ...t, widgets: t.widgets.map((w) => (w.i === it.i ? it : w)) })); setInspect(null); }} />
        )}
        {takeFrom && <TakeControl holder={takeFrom} onClose={() => setTakeFrom(null)} />}
        {askOverride && <OverrideConfirm onClose={() => setAskOverride(false)} />}
      </div>
    </EditCtx.Provider>
  );
}
