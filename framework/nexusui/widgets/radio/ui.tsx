import {
  OnOff, Readout, RoleRow, Sparkline, StateChip, Title, Unbound, Value, cx, useChannel, useDevice,
  type WidgetProps,
  LockChip, LockNote,
} from "@station/kit";

const SEGMENTS = 12;

/** Segmented link-quality bar: red when weak, amber when fair, green when good. */
function QualityBar({ ch }: { ch?: string }) {
  const { value } = useChannel(ch);
  const q = typeof value === "number" ? value : 0;
  const lit = Math.round((q / 100) * SEGMENTS);
  return (
    <div className="segbar">
      {Array.from({ length: SEGMENTS }, (_, k) => (
        <span key={k} className={cx("seg", k < lit && "lit", q < 25 && "hot", q >= 25 && q < 50 && "warm")} />
      ))}
    </div>
  );
}

export default function Radio({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  const q = useChannel(dev?.channels.quality);
  if (!dev) return <Unbound what="a radio link" />;
  return (
    <div className={`dev dev-${size}`}>
      <Title right={<StateChip ch={dev.channels.state} />}>{item.title || dev.label}</Title>
      {size === "s" ? (
        <>
          <div className="dev-hero"><Readout value={q.value} info={q.info} className="huge" /></div>
          <div className="dev-foot"><OnOff ch={dev.channels.enabled} onText="LINK ON" offText="LINK OFF" wide /></div>
        </>
      ) : (
        <>
          <div className="tri labeled">
            <div><span>SIGNAL</span><Value ch={dev.channels.rssi} className="big" /></div>
            <div><span>LOSS</span><Value ch={dev.channels.loss} className="big" /></div>
            <div><span>TX</span><Value ch={dev.channels.tx} className="big" /></div>
          </div>
          <QualityBar ch={dev.channels.quality} />
          <div className="center dim small">link quality <Value ch={dev.channels.quality} /></div>
          <div className="dev-foot"><OnOff ch={dev.channels.enabled} onText="LINK ON" offText="LINK OFF" wide /><LockChip ch={dev.channels.enabled} /></div>
          <LockNote ch={dev.channels.enabled} />
          <div className="rows"><RoleRow dev={dev} role="power" label="TX power" /></div>
          {size === "l" && <Sparkline ch={dev.channels.quality} height={56} />}
        </>
      )}
    </div>
  );
}
