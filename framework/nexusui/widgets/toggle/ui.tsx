import { Chip, LockChip, LockNote, Title, Unbound, WriterNote, cx, useBypass, useCanOperate, useChannel, useStation, type WidgetProps } from "@station/kit";

export default function Toggle({ item, size }: WidgetProps) {
  const st = useStation();
  const { value, info, pending, lock } = useChannel(item.bind);
  const op = useCanOperate();
  if (!item.bind) return <Unbound what="an on/off output" />;
  const on = value === true;
  const onText = item.options?.on_text || "ON";
  const offText = item.options?.off_text || "OFF";
  const bypass = useBypass();
  const can = op.ok && !!info?.writable && (!lock || bypass);
  const sw = (
    <button className={cx("switch", on && "on", pending && "pending")} disabled={!can}
      title={lock ? `Interlocked: ${lock}${bypass ? " (OVERRIDE active)" : ""}` : can ? `Switch ${on ? offText : onText}` : op.reason || "Read-only"}
      onClick={() => item.bind && st.write(item.bind, !on)}>
      <span className="switch-knob" />
    </button>
  );
  return (
    <div className={`toggle toggle-${size}`}>
      <Title right={<LockChip ch={item.bind} />}>{item.title || info?.label || item.bind}</Title>
      <div className="toggle-body">
        {size === "m" && (
          <div className="toggle-info">
            <Chip tone={on ? "active" : "off"}>{on ? onText : offText}</Chip>
            <WriterNote ch={item.bind} />
          </div>
        )}
        {sw}
      </div>
      {size === "s" && <div className="toggle-state"><Chip tone={on ? "active" : "off"}>{on ? onText : offText}</Chip></div>}
      <LockNote ch={item.bind} />
    </div>
  );
}
