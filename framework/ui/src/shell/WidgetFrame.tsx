import { Component, type ReactNode } from "react";
import { cx } from "../kit";
import type { WidgetItem, WidgetSpec } from "../lib/types";
import { sizeFor, widgetUIs } from "./registry";

export class Boundary extends Component<{ children: ReactNode; name: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="w-error">
          <b>{this.props.name} widget failed</b>
          <span>{this.state.error.message}</span>
          <button className="cmd" onClick={() => this.setState({ error: null })}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}

const SIZE_NAMES: Record<string, string> = { s: "S", m: "M", l: "L", t: "Tall", xl: "XL" };

export function WidgetFrame({ item, spec, editing, live, onPreset, onEdit, onRemove }: {
  item: WidgetItem;
  spec?: WidgetSpec;
  editing: boolean;
  live?: { w: number; h: number };
  onPreset: (size: string) => void;
  onEdit: () => void;
  onRemove: () => void;
}) {
  const Comp = widgetUIs[item.type];
  const w = live?.w ?? item.w;
  const h = live?.h ?? item.h;
  const size = sizeFor(spec, w, h);
  return (
    <div className={cx("wf", editing && "editing", `wt-${item.type}`, `ws-${size}`)}>
      <div className="wf-content">
        {Comp && spec ? (
          <Boundary name={spec.label}>
            <Comp item={item} spec={spec} size={size} cells={{ w, h }} />
          </Boundary>
        ) : (
          <div className="w-error"><b>Unknown widget “{item.type}”</b><span>No widget folder with that name.</span></div>
        )}
      </div>
      {editing && (
        <div className="wf-edit">
          <div className="wf-edit-bar">
            {spec?.sizes.map((s) => (
              <button key={s} className={cx("no-drag chipbtn", s === size && "sel")} title={`Resize to the ${SIZE_NAMES[s] ?? s} preset`}
                onClick={() => onPreset(s)}>{SIZE_NAMES[s] ?? s}</button>
            ))}
            <span className="grow" />
            <button className="no-drag iconbtn" title="Configure" onClick={onEdit}>⚙</button>
            <button className="no-drag iconbtn danger" title="Remove" onClick={onRemove}>✕</button>
          </div>
          <div className="wf-edit-size">{w}×{h}</div>
        </div>
      )}
    </div>
  );
}
