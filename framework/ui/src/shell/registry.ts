import type { ComponentType } from "react";
import type { WidgetProps, WidgetSpec } from "../lib/types";

// Every widget folder's ui.tsx, found at build time: framework widgets first, then the
// app's own widgets (an app widget with the same name replaces the framework one).
// The folder name is the widget type and matches the SPEC in that folder's backend.py.
const framework = import.meta.glob<{ default: ComponentType<WidgetProps> }>("@fw-widgets/*/ui.tsx", { eager: true });
const app = import.meta.glob<{ default: ComponentType<WidgetProps> }>("@app/widgets/*/ui.tsx", { eager: true });
const mods = { ...framework, ...app };

export const widgetUIs: Record<string, ComponentType<WidgetProps>> = {};
for (const [path, mod] of Object.entries(mods)) {
  const m = path.match(/widgets\/([^/]+)\/ui\.tsx$/);
  if (m) widgetUIs[m[1]] = mod.default;
}

/** The largest preset design that fits the box; the smallest preset if none fit. */
export function sizeFor(spec: WidgetSpec | undefined, w: number, h: number): string {
  if (!spec) return "m";
  const presets = spec.sizes.filter((s) => spec.size_cells[s]);
  if (!presets.length) return spec.default_size;
  const area = (s: string) => spec.size_cells[s][0] * spec.size_cells[s][1];
  const fits = presets.filter((s) => spec.size_cells[s][0] <= w && spec.size_cells[s][1] <= h);
  const pool = fits.length ? fits : presets;
  return pool.reduce((a, b) => ((fits.length ? area(b) > area(a) : area(b) < area(a)) ? b : a));
}
