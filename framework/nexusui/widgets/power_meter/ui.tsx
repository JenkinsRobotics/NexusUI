import { CmdButton, RoleRow, Sparkline, StateChip, Title, Unbound, Value, useDevice, type WidgetProps } from "@station/kit";

export default function PowerMeter({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  if (!dev) return <Unbound what="a power meter" />;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={size !== "s" ? <StateChip ch={dev.channels.zeroed} onText="ZEROED" offText="NOT ZEROED" /> : undefined}>
        {item.title || dev.label}
      </Title>
      <div className="dev-hero">
        <Value ch={dev.channels.watts} className="huge" />
        <span className="dim"><Value ch={dev.channels.volts} /></span>
      </div>
      {size !== "s" && (
        <>
          <div className="rows"><RoleRow dev={dev} role="scale" label="Calibration" /></div>
          <Sparkline ch={dev.channels.watts} height={40} />
        </>
      )}
      <div className="cmd-row"><CmdButton cmd={dev.commands.zero_cal} label={size === "s" ? "Zero" : undefined} /></div>
    </div>
  );
}
