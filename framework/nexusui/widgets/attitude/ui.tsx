import { Title, Unbound, useChannel, type WidgetProps } from "@station/kit";

const PX_PER_DEG = 2.2;
const num = (v: unknown) => (typeof v === "number" ? v : 0);

export default function Attitude({ item }: WidgetProps) {
  const [rollCh, pitchCh, headingCh] = item.binds ?? [];
  const roll = num(useChannel(rollCh).value);
  const pitch = num(useChannel(pitchCh).value);
  const heading = useChannel(headingCh).value;
  if (!rollCh || !pitchCh) return <Unbound what="roll, pitch and heading channels" />;
  const hdg = typeof heading === "number" ? ((Math.round(heading) % 360) + 360) % 360 : null;
  return (
    <div className="att">
      <Title sub={hdg !== null ? `HDG ${String(hdg).padStart(3, "0")}°` : undefined}>{item.title || "Attitude"}</Title>
      <svg className="att-svg" viewBox="-100 -100 200 200">
        <defs><clipPath id={`att-clip-${item.i}`}><circle r="88" /></clipPath></defs>
        <g clipPath={`url(#att-clip-${item.i})`}>
          <g transform={`rotate(${-roll}) translate(0 ${pitch * PX_PER_DEG})`}>
            <rect x="-300" y="-300" width="600" height="300" className="att-sky" />
            <rect x="-300" y="0" width="600" height="300" className="att-ground" />
            <line x1="-300" y1="0" x2="300" y2="0" className="att-horizon" />
            {[-30, -20, -10, 10, 20, 30].map((p) => (
              <g key={p}>
                <line x1={p % 20 ? -12 : -22} x2={p % 20 ? 12 : 22} y1={-p * PX_PER_DEG} y2={-p * PX_PER_DEG} className="att-ladder" />
                {p % 20 === 0 && <text x="28" y={-p * PX_PER_DEG + 3} className="att-ladder-text">{Math.abs(p)}</text>}
              </g>
            ))}
          </g>
        </g>
        <circle r="88" className="att-ring" />
        {[-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60].map((a) => (
          <line key={a} y1="-88" y2={a % 30 ? -82 : -78} transform={`rotate(${a})`} className="att-tick" />
        ))}
        <path d="M0,-78 L-5,-68 L5,-68 Z" transform={`rotate(${-roll})`} className="att-pointer" />
        <path d="M-46,0 L-16,0 L-8,8 M46,0 L16,0 L8,8" className="att-wings" />
        <circle r="2.6" className="att-dot" />
        <text x="-96" y="96" className="att-read">ROLL {roll.toFixed(1)}°</text>
        <text x="96" y="96" className="att-read" textAnchor="end">PITCH {pitch.toFixed(1)}°</text>
      </svg>
    </div>
  );
}
