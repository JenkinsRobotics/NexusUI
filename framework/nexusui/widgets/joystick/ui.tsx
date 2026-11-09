import { useRef, useState } from "react";
import { Title, Unbound, cx, useCanOperate, useChannel, useStation, type WidgetProps } from "@station/kit";

const SEND_MS = 100;   // at most ten writes a second while the stick is held

export default function Joystick({ item }: WidgetProps) {
  const st = useStation();
  const op = useCanOperate();
  const [xCh, yCh] = item.binds ?? [];
  const x = useChannel(xCh), y = useChannel(yCh);
  const pad = useRef<HTMLDivElement>(null);
  const sent = useRef(0);
  const [knob, setKnob] = useState<[number, number] | null>(null);
  if (!xCh || !yCh) return <Unbound what="two writable channels" />;
  const can = op.ok && !!x.info?.writable && !!y.info?.writable;
  // stick deflection is -1..1; each channel maps that onto its own min..max
  const scaled = (v: number, info = x.info) => {
    const lo = info?.min ?? -1, hi = info?.max ?? 1;
    return lo + ((v + 1) / 2) * (hi - lo);
  };
  const send = (dx: number, dy: number, force = false) => {
    const now = performance.now();
    if (!force && now - sent.current < SEND_MS) return;
    sent.current = now;
    st.write(xCh, Number(scaled(dx, x.info).toFixed(3)));
    st.write(yCh, Number(scaled(dy, y.info).toFixed(3)));
  };
  const move = (e: React.PointerEvent, force = false) => {
    const r = pad.current!.getBoundingClientRect();
    let dx = ((e.clientX - r.left) / r.width) * 2 - 1, dy = -(((e.clientY - r.top) / r.height) * 2 - 1);
    const m = Math.hypot(dx, dy);
    if (m > 1) { dx /= m; dy /= m; }
    setKnob([dx, dy]);
    send(dx, dy, force);
  };
  const release = () => { if (knob) { setKnob(null); send(0, 0, true); } };
  const [kx, ky] = knob ?? [0, 0];
  return (
    <div className="joy">
      <Title>{item.title || "Manual drive"}</Title>
      <div className="joy-body">
        <div ref={pad} className={cx("joy-pad", !can && "disabled", knob && "held")} title={can ? "Drag to drive" : op.reason}
          onPointerDown={(e) => { if (!can) return; (e.target as Element).setPointerCapture(e.pointerId); move(e, true); }}
          onPointerMove={(e) => knob && move(e)}
          onPointerUp={release} onPointerCancel={release}>
          <div className="joy-knob" style={{ left: `${50 + kx * 38}%`, top: `${50 - ky * 38}%` }} />
        </div>
      </div>
    </div>
  );
}
