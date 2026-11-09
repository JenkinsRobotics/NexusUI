export type Kind = "number" | "bool" | "enum" | "text";
export type Tone = "ok" | "warn" | "alarm" | "info" | "off" | "active";

export interface ChannelInfo {
  name: string;
  kind: Kind;
  label: string;
  unit: string;
  group: string;
  writable: boolean;
  fmt: "fixed" | "sci" | "int";
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  precision?: number;
  log_scale?: boolean;
  options?: string[];
  states?: Record<string, Tone>;
  limits?: { warn_high?: number; alarm_high?: number; warn_low?: number; alarm_low?: number };
  /** The channel has an interlock; its live reason arrives separately. */
  interlocked?: boolean;
}

export interface CommandInfo {
  name: string;
  label: string;
  confirm: boolean;
  danger: boolean;
  group: string;
  description?: string;
}

export interface DeviceInfo {
  id: string;
  type: string;
  label: string;
  channels: Record<string, string>;
  commands: Record<string, string>;
  sim: boolean;
}

export interface DiagramInfo { id: string; title: string; width: number; height: number; elements: Record<string, any>[] }

export interface StationInfo { id: string; name: string; addr: string; since: number }
export interface Writer { by: string; ts: number }
export interface LogEntry { ts: number; level: string; source: string; msg: string }
export interface Alert {
  id: number; key: string; level: "alarm" | "warn" | "info"; source: string; msg: string;
  ts: number; active: boolean; acked: boolean; count: number; cleared?: number;
}
export interface Control {
  mode: "lock" | "open"; holder: string | null; holder_name: string | null;
  override?: boolean; override_by?: string | null;
}
export interface Ack { ok: boolean; error?: string }

export interface SettingSpec {
  key: string; label: string; kind: "text" | "number" | "bool" | "select" | "textarea" | "channel" | "commands" | "diagram";
  default?: unknown; options?: string[]; min?: number; max?: number;
}

export interface WidgetSpec {
  type: string; label: string; description: string; category: string;
  sizes: string[]; default_size: string; size_cells: Record<string, [number, number]>;
  min_w: number; min_h: number;
  bind: "none" | "channel" | "channels" | "command" | "device";
  accepts: Kind[]; writable_only: boolean; settings: SettingSpec[];
}

/** One widget placed in a layout. Positions are grid cells. */
export interface WidgetItem {
  i: string; type: string; x: number; y: number; w: number; h: number;
  size?: string; title?: string;
  bind?: string; binds?: string[]; command?: string; device?: string;
  options?: Record<string, any>;
}

export interface Tab { id: string; title: string; widgets: WidgetItem[] }
export interface Layout { version: number; title?: string; tabs: Tab[]; saved_at?: number }

export interface WidgetProps {
  item: WidgetItem;
  spec: WidgetSpec;
  /** Largest size preset ("s" | "m" | "l" | "t" | "xl") whose design fits the widget's current box. */
  size: string;
  cells: { w: number; h: number };
}
