import type { ChannelInfo, Tone } from "./types";

export function fmtNumber(v: number, info?: ChannelInfo, precision?: number): string {
  if (info?.fmt === "sci") return v.toExponential(precision ?? info.precision ?? 2);
  if (info?.fmt === "int") return Math.round(v).toString();
  let p = precision ?? info?.precision;
  if (p === undefined) {
    const a = Math.abs(v);
    p = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : 3;
  }
  return v.toFixed(p);
}

export function fmtValue(v: unknown, info?: ChannelInfo, precision?: number): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return fmtNumber(v, info, precision);
  if (typeof v === "boolean") return v ? "ON" : "OFF";
  return String(v);
}

/** Tone from the channel's alarm limits (numbers) or state map (enums). */
export function toneOf(v: unknown, info?: ChannelInfo): Tone | undefined {
  if (!info || v === null || v === undefined) return undefined;
  if (info.kind === "enum" || info.kind === "text") return info.states?.[String(v)];
  if (info.kind === "bool") return v ? "active" : "off";
  if (typeof v !== "number" || !info.limits) return undefined;
  const l = info.limits;
  if ((l.alarm_high !== undefined && v >= l.alarm_high) || (l.alarm_low !== undefined && v <= l.alarm_low)) return "alarm";
  if ((l.warn_high !== undefined && v >= l.warn_high) || (l.warn_low !== undefined && v <= l.warn_low)) return "warn";
  return undefined;
}

export function ago(ts: number, nowSec: number): string {
  const s = Math.max(0, nowSec - ts);
  if (s < 2) return "just now";
  if (s < 60) return `${Math.floor(s)} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}

export function clock(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour12: false });
}

/** Fraction 0..1 of v across [min,max], on a log axis when asked. */
export function frac(v: number, min: number, max: number, log = false): number {
  if (log) {
    if (v <= 0 || min <= 0) return 0;
    return clamp((Math.log10(v) - Math.log10(min)) / (Math.log10(max) - Math.log10(min)), 0, 1);
  }
  return clamp((v - min) / (max - min || 1), 0, 1);
}

export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export const SERIES_COLORS = ["#5b9cff", "#f5a623", "#3ccf91", "#e05cf0", "#ff6b6b", "#4dd4e6", "#c7d36a", "#ff9f5a"];
