import {
  CmdButton, Readout, RoleRow, StateChip, Title, Unbound, Value, useChannel, useDevice, type WidgetProps,
} from "@station/kit";

export default function Servo({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const pos = useChannel(dev?.channels.position);
  const cmd = useChannel(dev?.channels.command);
  const lim = useChannel(dev?.channels.limit);
  if (!dev) return <Unbound what="a servo" />;
  const p = typeof pos.value === "number" ? pos.value : 0;
  const c = typeof cmd.value === "number" ? cmd.value : 0;
  const l = typeof lim.value === "number" ? lim.value : 100;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.state} />}>{item.title || dev.label}</Title>
      <div className="dev-hero">
        <Readout value={pos.value} info={pos.info} className="huge" />
        <div className="bar valve-bar">
          <div className="bar-fill" style={{ width: `${p}%` }} />
          <div className="bar-mark" style={{ left: `${c}%` }} title="Commanded" />
          {l < 100 && <div className="bar-limit" style={{ left: `${l}%` }} title="Travel limit" />}
        </div>
        <span className="dim small"><Value ch={dev.channels.drive} /> drive</span>
      </div>
      {size !== "s" && (
        <div className="rows">
          <RoleRow dev={dev} role="command" label="Position" />
          <RoleRow dev={dev} role="limit" label="Limit" />
        </div>
      )}
      <div className="cmd-row"><CmdButton cmd={dev.commands.park} label="PARK" /></div>
    </div>
  );
}
