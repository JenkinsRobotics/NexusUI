import { Sparkline, Title, Unbound, Value, WriterNote, useChannel, type WidgetProps } from "@station/kit";

export default function Stat({ item, size }: WidgetProps) {
  const { info } = useChannel(item.bind);
  if (!item.bind) return <Unbound />;
  const title = item.title || info?.label || item.bind;
  return (
    <div className={`stat stat-${size}`}>
      <Title>{title}</Title>
      <div className="stat-body">
        <Value ch={item.bind} className={size === "s" ? "big" : "huge"} />
        {size !== "s" && info?.kind === "number" && item.options?.trend !== false && (
          <Sparkline ch={item.bind} log={info.log_scale} height={44} />
        )}
      </div>
      {info?.writable && <WriterNote ch={item.bind} />}
    </div>
  );
}
