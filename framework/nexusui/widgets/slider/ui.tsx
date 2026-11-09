import { useState } from "react";
import {
  NumField, Readout, Sparkline, Title, Unbound, WriterNote, cx, fmtValue, useCanOperate, useChannel, useStation,
  type WidgetProps,
} from "@station/kit";

/** Setpoint slider. Writes on release, so dragging never floods the hardware. */
export default function Slider({ item, size }: WidgetProps) {
  const st = useStation();
  const { value, info, pending } = useChannel(item.bind);
  const rb = useChannel(item.options?.readback || undefined);
  const op = useCanOperate();
  const [drag, setDrag] = useState<number | null>(null);
  if (!item.bind) return <Unbound what="a writable number" />;
  const min = info?.min ?? 0;
  const max = info?.max ?? 100;
  const step = info?.step ?? (max - min) / 200;
  const v = typeof value === "number" ? value : min;
  const shown = drag ?? v;
  const can = op.ok && !!info?.writable;
  const commit = () => {
    if (drag !== null && drag !== v) st.write(item.bind!, drag);
    setDrag(null);
  };
  const nudge = (d: number) => st.write(item.bind!, Math.min(max, Math.max(min, +(v + d).toFixed(6))));
  return (
    <div className={`slider slider-${size}`}>
      <Title right={size === "l" ? <NumField ch={item.bind} /> : undefined}>{item.title || info?.label || item.bind}</Title>
      <div className="slider-readout">
        <Readout value={shown} info={info} className={cx("huge", drag !== null && "dragging")} />
        {item.options?.readback && (
          <span className="slider-rb">actual <Readout value={rb.value} info={rb.info} /></span>
        )}
      </div>
      <div className="slider-row">
        {size === "l" && <button className="nudge" disabled={!can} onClick={() => nudge(-step * 10)}>−</button>}
        <input type="range" className={cx("range", pending && "pending")} min={min} max={max} step={step}
          value={shown} disabled={!can} title={can ? "" : op.reason}
          style={{ ["--fill" as any]: `${((shown - min) / (max - min || 1)) * 100}%` }}
          onChange={(e) => setDrag(Number(e.target.value))}
          onPointerUp={commit} onKeyUp={commit} onBlur={commit} />
        {size === "l" && <button className="nudge" disabled={!can} onClick={() => nudge(step * 10)}>+</button>}
      </div>
      <div className="slider-scale"><span>{fmtValue(min, info)}</span><WriterNote ch={item.bind} /><span>{fmtValue(max, info)}</span></div>
      {size === "l" && <Sparkline ch={item.options?.readback || item.bind} height={40} />}
    </div>
  );
}
