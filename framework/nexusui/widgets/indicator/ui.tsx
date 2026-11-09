import { Chip, Led, Title, Unbound, WriterNote, toneOf, useChannel, type WidgetProps } from "@station/kit";

export default function Indicator({ item, size }: WidgetProps) {
  const { value, info } = useChannel(item.bind);
  if (!item.bind) return <Unbound what="a status channel" />;
  const isBool = info?.kind === "bool";
  const tone = isBool ? (value ? "ok" : "off") : toneOf(value, info) ?? "info";
  const on = isBool ? value === true : tone !== "off";
  const text = isBool ? (value ? item.options?.on_text || "ON" : item.options?.off_text || "OFF") : String(value ?? "—");
  return (
    <div className={`indicator indicator-${size}`}>
      <Title>{item.title || info?.label || item.bind}</Title>
      <div className="indicator-body">
        <Led on={on} tone={tone} size={size === "s" ? 34 : 40} />
        <div className="indicator-text">
          <Chip tone={tone}>{text}</Chip>
          {size === "m" && <WriterNote ch={item.bind} />}
        </div>
      </div>
    </div>
  );
}
