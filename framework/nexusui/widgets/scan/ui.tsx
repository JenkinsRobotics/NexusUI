import { useRef } from "react";
import { Title, Unbound, useChannel, useFrame, useStation, type WidgetProps } from "@station/kit";

const FRAME_MS = 1000 / 15;

export default function Scan({ item }: WidgetProps) {
  const st = useStation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef({ t: 0, raw: "" as unknown, w: 0, h: 0 });
  const { info } = useChannel(item.bind);
  const maxRange: number = Number(item.options?.max_range) || 20;
  const fov: number = Number(item.options?.fov) || 180;
  const unit: string = item.options?.unit ?? "m";

  useFrame((t) => {
    const c = canvas.current;
    if (!c || !item.bind || t - last.current.t < FRAME_MS) return;
    const raw = st.values.get(item.bind);
    const w = c.clientWidth, h = c.clientHeight;
    if (raw === last.current.raw && w === last.current.w && h === last.current.h) return;   // nothing new to draw
    last.current = { t, raw, w, h };
    const dpr = window.devicePixelRatio || 1;
    c.width = w * dpr; c.height = h * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    let ranges: number[] = [];
    try { ranges = JSON.parse(String(raw ?? "[]")); } catch { /* not a list yet */ }
    const full = fov > 200;
    const ox = w / 2, oy = full ? h / 2 : h - 14;
    const R = full ? Math.min(w, h) / 2 - 10 : Math.min(w / 2 - 8, h - 26);
    const half = (fov * Math.PI) / 360;
    const angle = (k: number) => -Math.PI / 2 - half + (2 * half * k) / Math.max(1, ranges.length - 1);
    g.clearRect(0, 0, w, h);
    g.font = "10px JetBrains Mono, monospace";
    // range rings
    for (let k = 1; k <= 3; k++) {
      g.beginPath();
      g.arc(ox, oy, (R * k) / 3, -Math.PI / 2 - half, -Math.PI / 2 + half);
      g.strokeStyle = "rgba(140,170,200,0.18)";
      g.stroke();
      g.fillStyle = "rgba(160,175,195,0.6)";
      g.fillText(`${Number(((maxRange * k) / 3).toPrecision(2))} ${unit}`, ox + 4, oy - (R * k) / 3 - 3);
    }
    if (!full) {
      g.beginPath();
      g.moveTo(ox + Math.cos(-Math.PI / 2 - half) * R, oy + Math.sin(-Math.PI / 2 - half) * R);
      g.lineTo(ox, oy);
      g.lineTo(ox + Math.cos(-Math.PI / 2 + half) * R, oy + Math.sin(-Math.PI / 2 + half) * R);
      g.stroke();
    }
    // free space, then the returns on its edge
    if (ranges.length > 1) {
      g.beginPath();
      g.moveTo(ox, oy);
      ranges.forEach((r, k) => {
        const d = (Math.min(r, maxRange) / maxRange) * R;
        g.lineTo(ox + Math.cos(angle(k)) * d, oy + Math.sin(angle(k)) * d);
      });
      g.closePath();
      const grd = g.createRadialGradient(ox, oy, 0, ox, oy, R);
      grd.addColorStop(0, "rgba(91,156,255,0.30)");
      grd.addColorStop(1, "rgba(91,156,255,0.05)");
      g.fillStyle = grd;
      g.fill();
      const nearest = Math.min(...ranges);
      ranges.forEach((r, k) => {
        if (r >= maxRange) return;
        const d = (r / maxRange) * R;
        g.beginPath();
        g.arc(ox + Math.cos(angle(k)) * d, oy + Math.sin(angle(k)) * d, r === nearest ? 3.5 : 2, 0, Math.PI * 2);
        g.fillStyle = r === nearest ? "#f5a623" : "#7fe3c0";
        g.fill();
      });
      g.fillStyle = "#f5a623";
      g.fillText(nearest < maxRange ? `nearest ${nearest.toFixed(1)} ${unit}` : "clear", 6, 12);
    }
    g.beginPath();
    g.moveTo(ox, oy - 7); g.lineTo(ox - 5, oy + 5); g.lineTo(ox + 5, oy + 5); g.closePath();
    g.fillStyle = "#e7ecf3";
    g.fill();
  });

  if (!item.bind) return <Unbound what="a scan channel" />;
  return (
    <div className="scan">
      <Title sub={`${fov}° · ${maxRange} ${unit}`}>{item.title || info?.label || "Scan"}</Title>
      <canvas ref={canvas} className="scan-canvas" />
    </div>
  );
}
