import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { SERIES_COLORS, Title, Unbound, Value, cx, expandBinds, useFrame, useStation, useTopic, useViewState, type WidgetProps } from "@station/kit";

const LIVE_HZ = 15;   // chart samples and redraws per second

export default function Chart({ item, cells }: WidgetProps) {
  const st = useStation();
  useTopic("catalog");
  const binds = expandBinds(st, item.binds?.length ? item.binds : item.bind ? [item.bind] : []);
  const win: number = Number(item.options?.window) || 60;
  // series hidden by clicking the legend; options.hidden is the starting point for every station
  const [hidden, setHidden] = useViewState<string[]>(item, "hidden", item.options?.hidden ?? []);
  const toggle = (b: string) => setHidden((h) => (h.includes(b) ? h.filter((x) => x !== b) : [...h, b]));
  const log: boolean = item.options?.log ?? (binds.length > 0 && binds.every((b) => st.channels.get(b)?.log_scale));
  const host = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const data = useRef<{ t: number[]; v: (number | null)[][] }>({ t: [], v: [] });
  const key = binds.join("|");
  const showLegend = cells.h >= 12;
  const epoch = st.history.epoch;   // the engine's history arrives on connect, which can be after this chart mounts

  useEffect(() => {
    const el = host.current;
    if (!el || !binds.length) return;
    data.current = st.history.slice(binds, st.now() - win);
    const css = getComputedStyle(el);
    const axis = css.getPropertyValue("--chart-axis").trim() || "#8a93a3";
    const grid = css.getPropertyValue("--chart-grid").trim() || "rgba(255,255,255,0.06)";
    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: el.clientHeight,
      legend: { show: false },
      cursor: { drag: { x: false, y: false }, points: { size: 6 } },
      scales: { x: { time: true }, y: log ? { distr: 3 } : { auto: true } },
      axes: [
        { stroke: axis, grid: { stroke: grid, width: 1 }, ticks: { stroke: grid }, size: 28, font: "11px Inter Variable, sans-serif" },
        {
          stroke: axis, grid: { stroke: grid, width: 1 }, ticks: { stroke: grid }, size: 54,
          font: "11px JetBrains Mono, monospace",
          values: log ? (_u, splits) => splits.map((v) => (v == null ? "" : v.toExponential(0))) : undefined,
        },
      ],
      series: [
        {},
        ...binds.map((b, k) => {
          const info = st.channels.get(b);
          return {
            label: info ? `${info.label}${info.unit ? ` (${info.unit})` : ""}` : b,
            stroke: SERIES_COLORS[k % SERIES_COLORS.length],
            width: 1.6,
            show: !hidden.includes(b),
            points: { show: false },
            fill: binds.length === 1 ? SERIES_COLORS[0] + "18" : undefined,
          };
        }),
      ],
    };
    const u = new uPlot(opts, [data.current.t, ...data.current.v] as uPlot.AlignedData, el);
    plot.current = u;
    const ro = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height: el.clientHeight }));
    ro.observe(el);
    return () => { ro.disconnect(); u.destroy(); plot.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, win, log, st, epoch]);

  useEffect(() => {
    binds.forEach((b, k) => plot.current?.setSeries(k + 1, { show: !hidden.includes(b) }));
  }, [hidden, binds]);   // eslint-disable-line react-hooks/exhaustive-deps

  useFrame(() => {
    const u = plot.current;
    if (!u || st.status !== "open") return;
    const now = st.now();
    const d = data.current;
    // Redraw with each new sample, not on every display frame: a full redraw per frame
    // cost about 10 % of a CPU core even while nothing on the chart was changing.
    if (d.t.length && now - d.t[d.t.length - 1] < 1 / LIVE_HZ) return;
    d.t.push(now);
    binds.forEach((b, k) => {
      const x = st.values.get(b);
      d.v[k] = d.v[k] ?? [];
      d.v[k].push(typeof x === "number" && (!log || x > 0) ? x : null);
    });
    let drop = 0;
    while (drop < d.t.length && d.t[drop] < now - win) drop++;
    if (drop) { d.t.splice(0, drop); d.v.forEach((s) => s.splice(0, drop)); }
    u.batch(() => {
      u.setData([d.t, ...d.v] as uPlot.AlignedData, true);
      u.setScale("x", { min: now - win, max: now });
    });
  });

  if (!binds.length) return <Unbound what="channels to trend" />;
  return (
    <div className="chart">
      <Title sub={`${win}s${log ? " · log" : ""}`}>{item.title || "Trend"}</Title>
      {showLegend && (
        <div className="chart-legend">
          {binds.map((b, k) => (
            <span key={b} className={cx("legend-item", hidden.includes(b) && "off")} title={`${b} · click to ${hidden.includes(b) ? "show" : "hide"}`}
              onClick={() => toggle(b)}>
              <span className="legend-dot" style={{ background: SERIES_COLORS[k % SERIES_COLORS.length] }} />
              {st.channels.get(b)?.label ?? b} <Value ch={b} />
            </span>
          ))}
        </div>
      )}
      <div className="chart-host" ref={host} />
    </div>
  );
}
