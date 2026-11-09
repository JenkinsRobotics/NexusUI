import {
  CmdButton, NumField, Readout, RoleRow, Sparkline, Title, Unbound, Value, useChannel, useDevice, type WidgetProps,
} from "@station/kit";

export default function Pump({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const fluid = useChannel(dev?.channels.fluid);
  const flow = useChannel(dev?.channels.flow);
  if (!dev) return <Unbound what="a pump" />;
  const isCtl = !!dev.channels.setpoint;
  return (
    <div className={`dev dev-${size}`}>
      <Title sub={`${isCtl ? "PUMP" : "METER"} · ${fluid.value ?? ""}`}>{item.title || dev.label}</Title>
      {size === "s" ? (
        <>
          <div className="dev-hero"><Readout value={flow.value} info={flow.info} className="huge" /></div>
          {isCtl && <div className="dev-foot"><span className="dim small">SP</span><NumField ch={dev.channels.setpoint} /></div>}
        </>
      ) : (
        <>
          <div className="dev-hero">
            <Readout value={flow.value} info={flow.info} className="huge" />
            <div className="duo small"><Value ch={dev.channels.pressure} /><Value ch={dev.channels.temp} /></div>
            <div className="dim small">total <Value ch={dev.channels.total} /></div>
          </div>
          <div className="cmd-row">
            <CmdButton cmd={dev.commands.zero} />
            <CmdButton cmd={dev.commands.reset_total} />
          </div>
          <div className="rows">
            {isCtl && <RoleRow dev={dev} role="setpoint" label="Setpoint" />}
            {isCtl && <RoleRow dev={dev} role="mode" label="Control" />}
            <RoleRow dev={dev} role="fluid" label="Fluid" />
          </div>
          {(size === "l") && <Sparkline ch={dev.channels.flow} height={48} />}
        </>
      )}
    </div>
  );
}
