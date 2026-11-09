import { ChannelRow, CmdButton, Title, Unbound, cx, expandBinds, useStation, useTopic, type WidgetProps } from "@station/kit";

/** Instrument-style panel: one row per channel, rendered by type, plus command buttons. */
export default function Panel({ item }: WidgetProps) {
  const st = useStation();
  useTopic("catalog");
  const binds = expandBinds(st, item.binds);
  const lockColumn = binds.some((b) => st.channels.get(b)?.interlocked);
  const commands: string[] = item.options?.commands ?? [];
  if (!binds.length && !commands.length) return <Unbound what="channels" />;
  return (
    <div className={cx("panel-w", item.options?.compact && "compact")}>
      <Title>{item.title || "Panel"}</Title>
      <div className="rows">
        {lockColumn && (
          <div className="row row-head">
            <span className="row-label">Name</span>
            <span className="row-lock">Interlock</span>
            <span className="row-value">Control</span>
          </div>
        )}
        {binds.map((b) => <ChannelRow key={b} ch={b} lockColumn={lockColumn} />)}
      </div>
      {commands.length > 0 && (
        <div className="cmd-row">{commands.map((c) => <CmdButton key={c} cmd={c} />)}</div>
      )}
    </div>
  );
}
