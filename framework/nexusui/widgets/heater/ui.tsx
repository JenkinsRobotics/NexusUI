import { OnOff, Readout, Sparkline, StateChip, Title, Unbound, frac, useChannel, useDevice, LockChip, LockNote, type WidgetProps } from "@station/kit";

export default function Heater({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const temp = useChannel(dev?.channels.temp);
  if (!dev) return <Unbound what="a heater" />;
  const f = typeof temp.value === "number" ? frac(temp.value, temp.info?.min ?? 0, temp.info?.max ?? 100) : 0;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.state} />}>{item.title || dev.label}</Title>
      <div className="dev-hero">
        <Readout value={temp.value} info={temp.info} className="huge" />
        <div className="bar"><div className="bar-fill heat" style={{ width: `${f * 100}%` }} /></div>
      </div>
      {size === "t" && <Sparkline ch={dev.channels.temp} height={48} color="#f5a623" />}
      <div className="dev-foot"><OnOff ch={dev.channels.heater} onText="HEATER ON" offText="HEATER OFF" wide /><LockChip ch={dev.channels.heater} /></div>
      <LockNote ch={dev.channels.heater} />
    </div>
  );
}
