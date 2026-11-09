import { useRef } from "react";
import { SERIES_COLORS, Title, Unbound, useFrame, useStation, useTopic, type WidgetProps } from "@station/kit";

const FRAME_MS = 1000 / 15;
const niceStep = (span: number) => {
  const raw = span / 6, mag = 10 ** Math.floor(Math.log10(raw)), n = raw / mag;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * mag;
};

export default function TrackMap({ item }: WidgetProps) {
  const st = useStation();
  useTopic("catalog");
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef(0);
  const binds = item.binds ?? [];
  const vehicles = Array.from({ length: Math.floor(binds.length / 3) }, (_, k) => binds.slice(k * 3, k * 3 + 3));
  const trail: number = Number(item.options?.trail) || 120;
  const fixed: number = Number(item.options?.extent) || 0;
  const unit: string = item.options?.unit ?? "m";
  const wpCh: string | undefined = item.options?.waypoints;

  useFrame((t) => {
    const c = canvas.current;
    if (!c || !vehicles.length || t - last.current < FRAME_MS) return;
    last.current = t;
    const w = c.clientWidth, h = c.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== w * dpr || c.height !== h * dpr) { c.width = w * dpr; c.height = h * dpr; }
    const g = c.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    let waypoints: number[][] = [];
    try { waypoints = wpCh ? JSON.parse(String(st.values.get(wpCh) ?? "[]")) : []; } catch { /* not a list yet */ }
    const trails = vehicles.map(([x, y]) => st.history.slice([x, y], st.now() - trail).v);
    const here = vehicles.map(([x, y, hd]) => [Number(st.values.get(x) ?? 0), Number(st.values.get(y) ?? 0), Number(st.values.get(hd) ?? 0)]);

    // view: fixed half-width around the origin, or fitted to everything drawn
    let cx = 0, cy = 0, ext = fixed;
    if (!fixed) {
      const xs: number[] = [], ys: number[] = [];
      waypoints.forEach(([x, y]) => { xs.push(x); ys.push(y); });
      here.forEach(([x, y]) => { xs.push(x); ys.push(y); });
      trails.forEach(([tx, ty]) => tx.forEach((x, k) => { if (x !== null && ty[k] !== null) { xs.push(x); ys.push(ty[k] as number); } }));
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
      ext = Math.max((x1 - x0) / 2 * (h / w > 1 ? 1 : 1), (y1 - y0) / 2 * (w / h), 5) * 1.18;
    }
    const scale = (w / 2) / ext;                       // pixels per unit; ext is the half-width
    const X = (x: number) => w / 2 + (x - cx) * scale;
    const Y = (y: number) => h / 2 - (y - cy) * scale;

    // grid
    const step = niceStep(ext * 2);
    g.lineWidth = 1;
    g.font = "10px JetBrains Mono, monospace";
    for (let x = Math.ceil((cx - ext) / step) * step; x <= cx + ext; x += step) {
      g.strokeStyle = Math.abs(x) < 1e-9 ? "rgba(140,170,200,0.30)" : "rgba(140,170,200,0.10)";
      g.beginPath(); g.moveTo(X(x), 0); g.lineTo(X(x), h); g.stroke();
    }
    const yExt = (h / 2) / scale;
    for (let y = Math.ceil((cy - yExt) / step) * step; y <= cy + yExt; y += step) {
      g.strokeStyle = Math.abs(y) < 1e-9 ? "rgba(140,170,200,0.30)" : "rgba(140,170,200,0.10)";
      g.beginPath(); g.moveTo(0, Y(y)); g.lineTo(w, Y(y)); g.stroke();
    }

    // planned route
    if (waypoints.length) {
      g.setLineDash([4, 5]);
      g.strokeStyle = "rgba(231,236,243,0.35)";
      g.beginPath();
      waypoints.forEach(([x, y], k) => (k ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y))));
      g.stroke();
      g.setLineDash([]);
      g.fillStyle = "rgba(231,236,243,0.55)";
      waypoints.forEach(([x, y]) => { g.beginPath(); g.arc(X(x), Y(y), 2.2, 0, Math.PI * 2); g.fill(); });
    }

    vehicles.forEach(([xCh], n) => {
      const color = SERIES_COLORS[n % SERIES_COLORS.length];
      const [tx, ty] = trails[n];
      g.strokeStyle = color;
      g.lineWidth = 2;
      g.globalAlpha = 0.75;
      g.beginPath();
      let pen = false;
      tx.forEach((x, k) => {
        const y = ty[k];
        if (x === null || y === null) { pen = false; return; }
        if (pen) g.lineTo(X(x), Y(y)); else { g.moveTo(X(x), Y(y)); pen = true; }
      });
      g.stroke();
      g.globalAlpha = 1;
      const [x, y, hd] = here[n];
      g.save();
      g.translate(X(x), Y(y));
      g.rotate((hd * Math.PI) / 180);                  // heading: degrees clockwise from north
      g.beginPath(); g.moveTo(0, -10); g.lineTo(7, 8); g.lineTo(0, 4); g.lineTo(-7, 8); g.closePath();
      g.fillStyle = color;
      g.shadowColor = color; g.shadowBlur = 10;
      g.fill();
      g.restore();
      const name = st.channels.get(xCh)?.group ?? xCh;
      g.fillStyle = color;
      g.font = "600 11px Inter Variable, sans-serif";
      const flip = X(x) > w - 90;                      // keep the label inside the right edge
      const lx = X(x) + (flip ? -12 : 12);
      const ly = Y(y) + (n % 2 ? 30 : -14);            // neighbours: one label above, the next below
      g.textAlign = flip ? "right" : "left";
      g.fillText(name.toUpperCase(), lx, ly);
      g.font = "10px JetBrains Mono, monospace";
      g.fillStyle = "rgba(200,210,225,0.8)";
      g.fillText(`${x.toFixed(1)}, ${y.toFixed(1)}`, lx, ly + 13);
      g.textAlign = "left";
    });

    // scale bar and north
    g.strokeStyle = g.fillStyle = "rgba(200,210,225,0.75)";
    g.lineWidth = 2;
    g.beginPath(); g.moveTo(12, h - 12); g.lineTo(12 + step * scale, h - 12); g.stroke();
    g.fillText(`${Number(step.toPrecision(2))} ${unit}`, 12, h - 18);
    g.beginPath(); g.moveTo(w - 16, 26); g.lineTo(w - 16, 10); g.lineTo(w - 20, 16); g.moveTo(w - 16, 10); g.lineTo(w - 12, 16); g.stroke();
    g.fillText("N", w - 19, 38);
  });

  if (!vehicles.length) return <Unbound what="x, y and heading channels" />;
  return (
    <div className="map">
      <Title sub={`${trail} s trail`}>{item.title || "Map"}</Title>
      <canvas ref={canvas} className="map-canvas" />
    </div>
  );
}
