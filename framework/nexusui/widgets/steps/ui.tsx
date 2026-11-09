import { Title, Unbound, cx, useChannel, type WidgetProps } from "@station/kit";

export default function Steps({ item, cells }: WidgetProps) {
  const { value, info } = useChannel(item.bind);
  if (!item.bind) return <Unbound what="a state channel" />;
  const steps = info?.options ?? [];
  const now = steps.indexOf(String(value));
  const tone = info?.states?.[String(value)];
  return (
    <div className={cx("steps", cells.w * 5.5 > cells.h * 1.6 && "steps-row")}>
      <Title>{item.title || info?.label || item.bind}</Title>
      <ol className="steps-list">
        {steps.map((s, k) => (
          <li key={s} className={cx(k < now && "done", k === now && "now", k === now && tone && `tone-${tone}`)}>
            <span className="steps-dot">{k < now ? "✓" : k + 1}</span>
            <span className="steps-label">{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
