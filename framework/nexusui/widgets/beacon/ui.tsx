import { OnOff, RoleRow, Title, Unbound, Value, useDevice, type WidgetProps } from "@station/kit";

export default function Beacon({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  if (!dev) return <Unbound what="a beacon" />;
  return (
    <div className={`dev dev-${size}`}>
      <Title>{item.title || dev.label}</Title>
      <div className="duo">
        <Value ch={dev.channels.freq} className="big" />
        <Value ch={dev.channels.level} className="big" />
      </div>
      <div className="dev-foot"><OnOff ch={dev.channels.output} onText="OUTPUT ON" offText="OUTPUT OFF" wide /></div>
      {size !== "s" && (
        <div className="rows">
          <RoleRow dev={dev} role="pattern" label="Pattern" />
          <RoleRow dev={dev} role="level" label="Level" />
          <RoleRow dev={dev} role="freq" label="Freq" />
          <RoleRow dev={dev} role="interval" label="Interval" />
          <RoleRow dev={dev} role="delay" label="Delay" />
        </div>
      )}
    </div>
  );
}
