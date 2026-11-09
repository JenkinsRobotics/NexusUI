import { useEffect, useRef } from "react";

/** One requestAnimationFrame loop shared by every canvas on the page. */
const drawers = new Set<(t: number) => void>();
let running = false;

function tick(t: number) {
  drawers.forEach((d) => {
    try { d(t); } catch (e) { console.error(e); }
  });
  if (drawers.size) requestAnimationFrame(tick);
  else running = false;
}

export function onFrame(fn: (t: number) => void) {
  drawers.add(fn);
  if (!running) {
    running = true;
    requestAnimationFrame(tick);
  }
  return () => { drawers.delete(fn); };
}

/** Call `draw` on every display frame while mounted. */
export function useFrame(draw: (t: number) => void) {
  const ref = useRef(draw);
  ref.current = draw;
  useEffect(() => onFrame((t) => ref.current(t)), []);
}
