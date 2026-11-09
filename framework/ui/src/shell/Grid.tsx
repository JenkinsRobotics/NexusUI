import { useLayoutEffect, useRef, useState } from "react";
import GridLayout, { type Layout as RGLItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import type { Tab, WidgetItem, WidgetSpec } from "../lib/types";
import { WidgetFrame } from "./WidgetFrame";

export interface GridConf { cols: number; row_px: number }
const MARGIN = 8;

/**
 * Free-form grid: fine cells, widgets float up to fill gaps (vertical compaction),
 * any edge can be dragged. Widgets redesign themselves live while being resized.
 */
export function Grid({ tab, specs, grid, editing, onLayout, onUserChange, onEdit, onRemove }: {
  tab: Tab;
  specs: Record<string, WidgetSpec>;
  grid: GridConf;
  editing: boolean;
  onLayout: (widgets: WidgetItem[]) => void;
  onUserChange: () => void;
  onEdit: (item: WidgetItem) => void;
  onRemove: (item: WidgetItem) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState<number | null>(null);
  const [live, setLive] = useState<{ i: string; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = host.current!;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const layout: RGLItem[] = tab.widgets.map((w) => {
    const spec = specs[w.type];
    return { i: w.i, x: w.x, y: w.y, w: w.w, h: w.h, minW: spec?.min_w ?? 3, minH: spec?.min_h ?? 5 };
  });

  const apply = (next: RGLItem[]) => {
    const pos = new Map(next.map((l) => [l.i, l]));
    let changed = false;
    const widgets = tab.widgets.map((w) => {
      const l = pos.get(w.i);
      if (!l || (l.x === w.x && l.y === w.y && l.w === w.w && l.h === w.h)) return w;
      changed = true;
      return { ...w, x: l.x, y: l.y, w: l.w, h: l.h };
    });
    if (changed) onLayout(widgets);
  };

  const preset = (item: WidgetItem, size: string) => {
    const cells = specs[item.type]?.size_cells[size];
    if (!cells) return;
    onLayout(tab.widgets.map((w) => (w.i === item.i ? { ...w, w: Math.min(cells[0], grid.cols), h: cells[1], size } : w)));
    onUserChange();
  };

  return (
    <div ref={host} className={`grid-host ${editing ? "editing" : ""}`}>
      {tab.widgets.length === 0 && (
        <div className="grid-empty">{editing ? "Add a widget to start this tab." : "This tab is empty. Click Edit layout to add widgets."}</div>
      )}
      {width !== null && <GridLayout
        layout={layout}
        cols={grid.cols}
        rowHeight={grid.row_px}
        width={width}
        margin={[MARGIN, MARGIN]}
        containerPadding={[MARGIN, MARGIN]}
        compactType="vertical"
        isDraggable={editing}
        isResizable={editing}
        resizeHandles={["se", "e", "s", "w"]}
        draggableCancel=".no-drag"
        useCSSTransforms
        onLayoutChange={apply}
        onResize={(_l, _o, n) => setLive({ i: n.i, w: n.w, h: n.h })}
        onResizeStop={() => { setLive(null); onUserChange(); }}
        onDragStop={() => onUserChange()}
      >
        {tab.widgets.map((w) => (
          <div key={w.i}>
            <WidgetFrame
              item={w}
              spec={specs[w.type]}
              editing={editing}
              live={live?.i === w.i ? live : undefined}
              onPreset={(s) => preset(w, s)}
              onEdit={() => onEdit(w)}
              onRemove={() => onRemove(w)}
            />
          </div>
        ))}
      </GridLayout>}
    </div>
  );
}
