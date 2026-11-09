import { Readout, Sparkline, Title, Unbound, fmtValue, frac, toneOf, useChannel, type WidgetProps } from "@station/kit";

const R = 40;
const C = 2 * Math.PI * R;
const L = C * 0.75; // 270 degree arc

function Arc({ from, to, cls, width = 8 }: { from: number; to: number; cls: string; width?: number }) {
  return (
    <circle cx="50" cy="50" r={R} className={cls} strokeWidth={width} fill="none"
      strokeDasharray={`${Math.max(0, to - from) * L} ${C}`} strokeDashoffset={-from * L}
      transform="rotate(135 50 50)" />
  );
}

export default function Gauge({ item, size }: WidgetProps) {
  const { value, info } = useChannel(item.bind);
  if (!item.bind) return <Unbound />;
  const min = item.options?.min ?? info?.min ?? 0;
  const max = item.options?.max ?? info?.max ?? 100;
  const log = !!info?.log_scale;
  const f = typeof value === "number" ? frac(value, min, max, log) : 0;
  const lim = info?.limits ?? {};
  const tone = toneOf(value, info);
  const title = item.title || info?.label || item.bind;
  const fw = lim.warn_high !== undefined ? frac(lim.warn_high, min, max, log) : undefined;
  const fa = lim.alarm_high !== undefined ? frac(lim.alarm_high, min, max, log) : undefined;

  const dial = (
    <svg viewBox="0 0 100 100" className="gauge-svg">
      <Arc from={0} to={1} cls="gauge-track" />
      {fw !== undefined && <Arc from={fw} to={fa ?? 1} cls="gauge-band warn" width={3} />}
      {fa !== undefined && <Arc from={fa} to={1} cls="gauge-band alarm" width={3} />}
      <Arc from={0} to={f} cls={`gauge-value ${tone ? `tone-${tone}` : ""}`} />
      {size === "l" && Array.from({ length: 11 }, (_, k) => {
        const a = ((135 + k * 27) * Math.PI) / 180;
        return <line key={k} x1={50 + Math.cos(a) * 30} y1={50 + Math.sin(a) * 30}
          x2={50 + Math.cos(a) * 33} y2={50 + Math.sin(a) * 33} className="gauge-tick" />;
      })}
    </svg>
  );

  return (
    <div className={`gauge gauge-${size}`}>
      <Title>{title}</Title>
      <div className="gauge-body">
        <div className="gauge-dial">
          {dial}
          <div className="gauge-center">
            <Readout value={value} info={info} unit={false} className={size === "s" ? "big" : "huge"} />
            <span className="gauge-unit">{info?.unit}</span>
          </div>
        </div>
        {size === "m" && (
          <div className="gauge-side">
            <div className="kv"><span>Min</span><b>{fmtValue(min, info)}</b></div>
            <div className="kv"><span>Max</span><b>{fmtValue(max, info)}</b></div>
            {lim.warn_high !== undefined && <div className="kv tone-warn"><span>Warn</span><b>{fmtValue(lim.warn_high, info)}</b></div>}
            {lim.alarm_high !== undefined && <div className="kv tone-alarm"><span>Alarm</span><b>{fmtValue(lim.alarm_high, info)}</b></div>}
          </div>
        )}
      </div>
      {size === "l" && <Sparkline ch={item.bind} log={log} height={40} />}
    </div>
  );
}
