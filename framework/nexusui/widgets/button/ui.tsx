import { CmdButton, Title, Unbound, useCommand, type WidgetProps } from "@station/kit";

export default function Button({ item, size }: WidgetProps) {
  const info = useCommand(item.command);
  if (!item.command) return <Unbound what="a command" />;
  return (
    <div className={`button-w button-${size}`}>
      {size === "m" && <Title>{item.title || info?.label || item.command}</Title>}
      <CmdButton cmd={item.command} big label={size === "s" ? item.title || info?.label : undefined} />
      {size === "m" && info?.description && <div className="dim small">{info.description}</div>}
      {info?.danger && <div className="dim small center">Press and hold</div>}
    </div>
  );
}
