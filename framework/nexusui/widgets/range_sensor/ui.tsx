import { OnOff, Readout, RoleRow, Sparkline, StateChip, Title, Unbound, useChannel, useDevice, LockChip, LockNote, type WidgetProps } from "@station/kit";

export default function RangeSensor({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const r = useChannel(dev?.channels.range);
  if (!dev) return <Unbound what="a range sensor" />;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.state} />}>{item.title || dev.label}</Title>
      <div className="dev-hero">
        <Readout value={r.value} info={r.info} className="huge" />
      </div>
      {size !== "s" && (
        <div className="rows">
          <RoleRow dev={dev} role="signal" label="Signal strength" />
        </div>
      )}
      {size === "t" && <Sparkline ch={dev.channels.range} height={56} />}
      <div className="dev-foot"><OnOff ch={dev.channels.emit} onText="EMITTER ON" offText="EMITTER OFF" wide /><LockChip ch={dev.channels.emit} /></div>
      <LockNote ch={dev.channels.emit} />
    </div>
  );
}
