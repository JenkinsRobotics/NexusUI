import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import type { ChanSnap, Station, Topic } from "./store";
import { ls } from "./ls";
import type { ChannelInfo, CommandInfo, DeviceInfo, WidgetItem } from "./types";

export const StationCtx = createContext<Station>(null!);
export const EditCtx = createContext(false);

export const useStation = () => useContext(StationCtx);
export const useEditing = () => useContext(EditCtx);

/**
 * View state a widget keeps across page reloads, per browser: which series are hidden,
 * which section is open, and so on. Keyed by layout and widget, so two charts in one
 * layout do not share it. Not synced to other stations and not part of the saved layout.
 */
export function useViewState<T>(item: WidgetItem, key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const st = useStation();
  const k = `vp.view.${st.layoutName}.${item.i}.${key}`;
  const [v, setV] = useState<T>(() => {
    const s = ls.get(k);
    if (s === null) return initial;
    try { return JSON.parse(s) as T; } catch { return initial; }
  });
  const set = useCallback((nv: T | ((prev: T) => T)) => setV((prev) => {
    const next = typeof nv === "function" ? (nv as (p: T) => T)(prev) : nv;
    ls.set(k, JSON.stringify(next));
    return next;
  }), [k]);
  return [v, set];
}

/**
 * The channels a widget is bound to, with wildcards expanded: ``rtd.*`` means every
 * channel whose name starts with ``rtd.``. Callers subscribe to the catalog so the
 * list follows the engine.
 */
export function expandBinds(st: Station, binds: string[] | undefined): string[] {
  const out: string[] = [];
  for (const b of binds ?? []) {
    if (!b.includes("*")) { out.push(b); continue; }
    const re = new RegExp("^" + b.split("*").map((p) => p.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join(".*") + "$");
    for (const name of [...st.channels.keys()].sort()) if (re.test(name) && !out.includes(name)) out.push(name);
  }
  return out;
}

/** Re-render when a topic changes (connection, control, alerts, ...). */
export function useTopic(topic: Topic) {
  const st = useStation();
  const sub = useCallback((fn: () => void) => st.subscribe(topic, fn), [st, topic]);
  return useSyncExternalStore(sub, () => st.version(topic));
}

const EMPTY: ChanSnap = { value: undefined, pending: false };

/** Live value of one channel. Only this widget re-renders when it changes. */
export function useChannel(name?: string): ChanSnap & { info?: ChannelInfo } {
  const st = useStation();
  useTopic("catalog");
  const sub = useCallback((fn: () => void) => (name ? st.subscribeChannel(name, fn) : () => {}), [st, name]);
  const snap = useSyncExternalStore(sub, () => (name ? st.channelSnap(name) : EMPTY));
  return { ...snap, info: name ? st.channels.get(name) : undefined };
}

export function useDevice(id?: string): DeviceInfo | undefined {
  const st = useStation();
  useTopic("catalog");
  return id ? st.devices.get(id) : undefined;
}

export function useCommand(name?: string): CommandInfo | undefined {
  const st = useStation();
  useTopic("catalog");
  return name ? st.commands.get(name) : undefined;
}

/** Whether this station may operate controls right now, and why not. */
export function useCanOperate(): { ok: boolean; reason: string } {
  const st = useStation();
  const editing = useEditing();
  useTopic("control");
  useTopic("conn");
  if (editing) return { ok: false, reason: "Finish editing the layout to operate" };
  if (st.status !== "open") return { ok: false, reason: "Disconnected from engine" };
  if (!st.inControl) {
    const who = st.control.holder_name;
    return { ok: false, reason: who ? `View only. ${who} has control.` : "View only. Take control to operate." };
  }
  return { ok: true, reason: "" };
}

/** True while this station operates with the interlock override on. */
export function useBypass() {
  const st = useStation();
  useTopic("control");
  return st.bypass;
}

/** Re-render every `ms` (for "3 s ago" labels). */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}
