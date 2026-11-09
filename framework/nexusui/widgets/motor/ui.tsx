import {
  OnOff, Readout, RoleRow, StateChip, Title, Unbound, frac, useChannel, useDevice, type WidgetProps,
  LockChip, LockNote,
} from "@station/kit";

export default function Motor({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const rpm = useChannel(dev?.channels.rpm);
  if (!dev) return <Unbound what="a motor" />;
  const f = typeof rpm.value === "number" ? frac(rpm.value, 0, rpm.info?.max ?? 1) : 0;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.status} />}>{item.title || dev.label}</Title>
      <div className="dev-hero">
        <Readout value={rpm.value} info={rpm.info} className="huge" />
        <div className="bar"><div className="bar-fill" style={{ width: `${f * 100}%` }} /></div>
      </div>
      {size === "s" ? (
        <div className="dev-foot"><OnOff ch={dev.channels.on} onText="RUNNING" offText="STOPPED" wide /><LockChip ch={dev.channels.on} /></div>
      ) : (
        <div className="rows">
          <RoleRow dev={dev} role="current" label="Current" />
          <div className="row"><span className="row-label">Run<LockNote ch={dev.channels.on} /></span>
            <span className="row-value"><LockChip ch={dev.channels.on} /><OnOff ch={dev.channels.on} onText="RUNNING" offText="STOPPED" /></span></div>
          <RoleRow dev={dev} role="eco_mode" label="Eco mode" />
          <RoleRow dev={dev} role="eco_speed" label="Eco cap" />
          <RoleRow dev={dev} role="locked" label="Panel lock" />
        </div>
      )}
    </div>
  );
}
