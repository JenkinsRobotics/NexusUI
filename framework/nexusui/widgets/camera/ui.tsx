import { useRef } from "react";
import {
  CmdButton, RoleRow, StateChip, Title, Unbound, useChannel, useDevice, useFrame, useStation,
  type WidgetProps,
} from "@station/kit";

const FRAME_MS = 1000 / 20;   // redraw rate of the simulated view

/**
 * Simulated camera view rendered in the browser from the brightness channel:
 * a ground grid sliding past and a warm target that the tracker boxes.
 * A real camera would show <img src={stream_url}> (MJPEG) in place of the canvas.
 */
function CameraView({ dev }: { dev: { channels: Record<string, string> } }) {
  const st = useStation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const glow = useRef(0);
  const last = useRef(0);
  const noise = useRef<HTMLCanvasElement | null>(null);
  const fps = useChannel(dev.channels.fps);
  const locked = useChannel(dev.channels.locked);
  const armed = useChannel(dev.channels.armed);

  useFrame((t) => {
    const c = canvas.current;
    if (!c || t - last.current < FRAME_MS) return;
    last.current = t;
    const w = c.clientWidth, h = c.clientHeight;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    const g = c.getContext("2d")!;
    const b = Number(st.values.get(dev.channels.brightness) ?? 0);
    glow.current += (b - glow.current) * 0.35;  // smooth between telemetry frames
    const k = glow.current;
    const sky = g.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, "#04090d");
    sky.addColorStop(1, "#07141a");
    g.fillStyle = sky;
    g.fillRect(0, 0, w, h);
    // ground grid sliding toward the viewer
    const horizon = h * 0.3;
    g.strokeStyle = "rgba(90,170,190,0.16)";
    g.lineWidth = 1;
    g.beginPath();
    for (let n = -8; n <= 8; n++) { g.moveTo(w / 2 + n * w * 0.03, horizon); g.lineTo(w / 2 + n * w * 0.22, h); }
    const slide = (t / 2600) % 1;
    for (let n = 0; n < 7; n++) {
      const y = horizon + (h - horizon) * ((n + slide) / 7) ** 2;
      g.moveTo(0, y); g.lineTo(w, y);
    }
    g.moveTo(0, horizon); g.lineTo(w, horizon);
    g.stroke();
    // target: a warm spot that drifts a little in the frame
    const cx = w * (0.56 + Math.sin(t / 2300) * 0.07), cy = h * (0.6 + Math.cos(t / 1700) * 0.05);
    const r = Math.max(4, h * 0.16 * Math.min(1, 0.35 + k * 1.3));
    if (k > 0.06) {
      const grd = g.createRadialGradient(cx, cy, 0, cx, cy, r);
      grd.addColorStop(0, `rgba(255,244,214,${Math.min(1, 0.4 + k * 1.6)})`);
      grd.addColorStop(0.3, `rgba(255,176,72,${Math.min(1, 0.25 + k * 1.2)})`);
      grd.addColorStop(0.65, `rgba(220,90,40,${Math.min(0.6, 0.1 + k * 0.6)})`);
      grd.addColorStop(1, "rgba(120,40,10,0)");
      g.fillStyle = grd;
      g.beginPath(); g.ellipse(cx, cy, r * 1.25, r * 0.8, 0, 0, Math.PI * 2); g.fill();
    }
    // sensor noise
    if (!noise.current) {
      const n = document.createElement("canvas");
      n.width = n.height = 128;
      const ng = n.getContext("2d")!;
      const img = ng.createImageData(128, 128);
      for (let i = 0; i < img.data.length; i += 4) {
        const v = Math.random() * 40;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = 40;
      }
      ng.putImageData(img, 0, 0);
      noise.current = n;
    }
    g.globalCompositeOperation = "lighter";
    g.fillStyle = g.createPattern(noise.current, "repeat")!;
    g.save(); g.translate((t * 0.13) % 128, (t * 0.07) % 128); g.fillRect(-128, -128, w + 256, h + 256); g.restore();
    g.globalCompositeOperation = "source-over";
    // tracker box
    const bw = h * 0.26, bh = h * 0.26, bx = cx - bw / 2, by = cy - bh / 2;
    const on = locked.value === true;
    g.strokeStyle = on ? "#3ccf91" : armed.value ? "rgba(60,207,145,0.6)" : "rgba(200,200,200,0.35)";
    g.lineWidth = 1.5;
    g.strokeRect(bx, by, bw, bh);
    g.beginPath(); g.moveTo(cx, by + 4); g.lineTo(cx, by + bh - 4);
    g.moveTo(bx + 4, cy); g.lineTo(bx + bw - 4, cy); g.stroke();
    g.font = "600 12px JetBrains Mono, monospace";
    g.fillStyle = on ? "#3ccf91" : "rgba(200,200,200,0.6)";
    g.fillText(`${(k * 100).toFixed(0)} / ${armed.value ? "armed" : "idle"}${on ? "  LOCK" : ""}`, bx, by - 6);
    g.fillStyle = "#f5a623";
    g.fillText(`${Math.round(Number(fps.value ?? 0))} fps`, 8, h - 10);
  });
  return <canvas ref={canvas} className="cam-canvas" />;
}

export default function Camera({ item, size }: WidgetProps) {
  const dev = useDevice(item.device);
  if (!dev) return <Unbound what="a camera" />;
  const controls = (
    <div className="cam-controls">
      <div className="chip-row">
        <StateChip ch={dev.channels.armed} onText="ARMED" offText="DISARMED" />
        <StateChip ch={dev.channels.locked} onText="LOCKED" offText="SEARCHING" />
        <StateChip ch={dev.channels.calibrated} onText="CALIBRATED" offText="NOT CALIBRATED" />
      </div>
      <div className="rows">
        <RoleRow dev={dev} role="armed" label="Tracker" />
        <RoleRow dev={dev} role="exposure" label="Exposure" />
      </div>
      <div className="cmd-col">
        <CmdButton cmd={dev.commands.auto_expose} label="1. Auto-Expose" />
        <CmdButton cmd={dev.commands.set_background} label="2. Set Background" />
        <CmdButton cmd={dev.commands.set_reference} label="3. Set Target Reference" />
      </div>
    </div>
  );
  return (
    <div className={`dev cam cam-${size}`}>
      <Title right={<StateChip ch={dev.channels.locked} onText="LOCKED" offText="SEARCHING" />}>{item.title || dev.label}</Title>
      <div className="cam-body">
        <CameraView dev={dev} />
        {size !== "m" && controls}
      </div>
    </div>
  );
}
