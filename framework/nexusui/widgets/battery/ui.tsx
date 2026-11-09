import {
  CmdButton, Readout, RoleRow, StateChip, Title, Unbound, Value, cx, toneOf, useChannel, useDevice, type WidgetProps,
} from "@station/kit";

export default function Battery({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const soc = useChannel(dev?.channels.soc);
  if (!dev) return <Unbound what="a battery" />;
  const level = typeof soc.value === "number" ? Math.max(0, Math.min(100, soc.value)) : 0;
  const tone = toneOf(soc.value, soc.info);
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.state} />}>{item.title || dev.label}</Title>
      <div className="dev-hero">
        <Readout value={soc.value} info={soc.info} className="huge" />
        <div className={cx("batt", tone && `tone-${tone}`)}>
          <div className="batt-fill" style={{ width: `${level}%` }} />
        </div>
        <span className="dim small"><Value ch={dev.channels.remaining} /> remaining</span>
      </div>
      {size !== "s" && (
        <div className="rows">
          <RoleRow dev={dev} role="voltage" label="Voltage" />
          <RoleRow dev={dev} role="current" label="Current" />
          <RoleRow dev={dev} role="temp" label="Temperature" />
        </div>
      )}
      {size === "t" && <div className="cmd-row"><CmdButton cmd={dev.commands.swap} /></div>}
    </div>
  );
}
