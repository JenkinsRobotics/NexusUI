import { Readout, Title, Unbound, cx, frac, toneOf, useChannel, type WidgetProps } from "@station/kit";

const TICKS = 5;

export default function Bar({ item }: WidgetProps) {
  const { value, info } = useChannel(item.bind);
  const target = useChannel(item.options?.target);
  if (!item.bind) return <Unbound />;
  const min: number = item.options?.min ?? info?.min ?? 0;
  const max: number = item.options?.max ?? info?.max ?? 100;
  const invert = !!item.options?.invert;
  const horizontal = !!item.options?.horizontal;
  const f = typeof value === "number" ? frac(value, min, max) : 0;
  const ft = typeof target.value === "number" ? frac(target.value, min, max) : undefined;
  const tone = toneOf(value, info);
  // distance of a 0..1 scale position from the start edge (top, or left when horizontal)
  const at = (x: number) => `${(horizontal ? x : invert ? x : 1 - x) * 100}%`;
  const edge = horizontal ? "left" : "top";
  const fill = horizontal ? { left: 0, width: `${f * 100}%` }
    : invert ? { top: 0, height: `${f * 100}%` } : { bottom: 0, height: `${f * 100}%` };
  const ticks = Array.from({ length: TICKS }, (_, k) => min + ((max - min) * k) / (TICKS - 1));
  return (
    <div className={cx("barg", horizontal ? "barg-h" : "barg-v")}>
      <Title>{item.title || info?.label || item.bind}</Title>
      <div className="barg-body">
        <div className="barg-scale">
          {ticks.map((t) => (
            <span key={t} style={{ [edge]: at(frac(t, min, max)) }}>{Number(t.toPrecision(3))}</span>
          ))}
        </div>
        <div className="barg-track">
          <div className={cx("barg-fill", tone && `tone-${tone}`)} style={fill} />
          {ft !== undefined && <div className="barg-target" style={{ [edge]: at(ft) }} title="Target" />}
        </div>
      </div>
      <Readout value={value} info={info} className="big" />
    </div>
  );
}
