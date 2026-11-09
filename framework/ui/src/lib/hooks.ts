import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import type { ChanSnap, Station, Topic } from "./store";
import type { ChannelInfo, CommandInfo, DeviceInfo } from "./types";

export const StationCtx = createContext<Station>(null!);
export const EditCtx = createContext(false);

export const useStation = () => useContext(StationCtx);
export const useEditing = () => useContext(EditCtx);

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
