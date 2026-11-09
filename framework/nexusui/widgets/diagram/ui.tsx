import {
  Title, Unbound, cx, fmtValue, toneOf, useBypass, useCanOperate, useChannel, useStation, useTopic, type WidgetProps,
} from "@station/kit";

type El = Record<string, any>;

const truthy = (v: unknown) => (typeof v === "number" ? v > 0.01 : !!v);

/** Pipe flows while any group of channels is all on. `when` is a list of groups (or one flat group). */
function useFlowing(when?: (string | string[])[]) {
  const st = useStation();
  const groups: string[][] = !when?.length ? [] : typeof when[0] === "string" ? [when as string[]] : (when as string[][]);
  const names = [...new Set(groups.flat())];
  // the channel list is fixed per pipe, so the hook count is stable
  const vals = new Map(names.map((c) => [c, useChannel(c).value])); // eslint-disable-line react-hooks/rules-of-hooks
  return st.status === "open" && groups.some((g) => g.every((c) => truthy(vals.get(c))));
}

function Pipe({ e }: { e: El }) {
  const flowing = useFlowing(e.when);
  const d = e.points.map((p: number[], k: number) => `${k ? "L" : "M"}${p[0]},${p[1]}`).join(" ");
  return (
    <g className={cx("dgm-pipe", `pipe-${e.type}`, flowing && "flowing")}>
      <path d={d} className="pipe-base" />
      {flowing && <path d={d} className="pipe-flow" />}
    </g>
  );
}

function Lines({ chs, x, y, size = 13 }: { chs: string[]; x: number; y: number; size?: number }) {
  return <>{chs.map((c, k) => <ValueText key={c} ch={c} x={x} y={y + k * (size + 4)} size={size} />)}</>;
}

function ValueText({ ch, x, y, size = 13, anchor = "middle" }: { ch: string; x: number; y: number; size?: number; anchor?: string }) {
  const { value, info } = useChannel(ch);
  const tone = toneOf(value, info);
  const unit = info?.unit && value !== null && value !== undefined ? ` ${info.unit}` : "";
  return (
    <text x={x} y={y} className={cx("dgm-val", tone && `tone-${tone}`)} fontSize={size} textAnchor={anchor as any}>
      {fmtValue(value, info)}{unit}
    </text>
  );
}

function StateText({ ch, x, y }: { ch: string; x: number; y: number }) {
  const { value, info } = useChannel(ch);
  const tone = toneOf(value, info);
  return <text x={x} y={y} className={cx("dgm-state", tone && `tone-${tone}`)} textAnchor="middle">{fmtValue(value, info)}</text>;
}

function Vessel({ e }: { e: El }) {
  const glow = useChannel(e.glow).value === true;
  const cx0 = e.x + e.w / 2;
  return (
    <g className="dgm-vessel">
      <rect x={e.x} y={e.y} width={e.w} height={e.h} rx={Math.min(40, e.h / 3)} className="vessel-body" />
      {glow && <ellipse cx={cx0} cy={e.y + e.h * 0.62} rx={e.w * 0.22} ry={e.h * 0.16} className="vessel-glow" />}
      <text x={cx0} y={e.y + 30} className="dgm-label big" textAnchor="middle">{e.label}</text>
      {e.value && <ValueText ch={e.value} x={cx0} y={e.y + e.h / 2 + 8} size={Math.min(26, e.w / 8)} />}
      {e.state && <StateText ch={e.state} x={cx0} y={e.y + e.h / 2 + 34} />}
      {e.values?.length > 0 && <Lines chs={e.values} x={cx0} y={e.y + e.h / 2 + 56} size={12} />}
    </g>
  );
}

function Equipment({ e }: { e: El }) {
  const st = useStation();
  const on = useChannel(e.on);
  const state = useChannel(e.state);
  const op = useCanOperate();
  const locked = !!on.lock;
  const bypass = useBypass();
  const running = e.on ? on.value === true : truthy(state.value) && toneOf(state.value, state.info) !== "off";
  const tone = e.state ? toneOf(state.value, state.info) : running ? "ok" : "off";
  const clickable = !!e.on && !!on.info?.writable;
  const can = clickable && op.ok && (!locked || bypass);
  const spin = e.type === "motor" && running;
  const title = `${e.label}${e.state ? `: ${fmtValue(state.value, state.info)}` : e.on ? `: ${on.value ? "ON" : "OFF"}` : ""}` +
    (locked ? ` · interlocked: ${on.lock}` : clickable ? (can ? " (click to switch)" : ` (${op.reason})`) : "");
  return (
    <g className={cx("dgm-equip", `eq-${e.type}`, running && "running", tone && `tone-${tone}`, can && "clickable", on.pending && "pending")}
      onClick={() => can && e.on && st.write(e.on, !on.value)}>
      <title>{title}</title>
      <rect x={e.x} y={e.y} width={e.w} height={e.h} rx={10} className="equip-body" />
      {e.type === "motor" && (
        <g transform={`translate(${e.x + e.w - 16} ${e.y + 16})`}>
          <g className={cx("fan", spin && "spin")}>
            {[0, 60, 120, 180, 240, 300].map((a) => <path key={a} d="M0,0 L9,-3 L9,3 Z" transform={`rotate(${a})`} />)}
          </g>
        </g>
      )}
      {e.type === "pump" && <circle cx={e.x + 13} cy={e.y + 16} r={4.5} className="equip-led" />}
      <text x={e.x + (e.type === "pump" ? 23 : 10)} y={e.y + 20} className="dgm-label">{e.label}</text>
      {e.sub && <text x={e.x + 10} y={e.y + 34} className="dgm-sub">{e.sub}</text>}
      {e.state && <StateText ch={e.state} x={e.x + e.w / 2} y={e.y + e.h - 10} />}
      {locked && <text x={e.x + e.w - 4} y={e.y - 5} className="valve-lock" textAnchor="end">LOCK</text>}
      <Lines chs={e.values ?? []} x={e.x + e.w / 2} y={e.y + (e.sub ? 52 : 42)} size={12} />
    </g>
  );
}

function Valve({ e }: { e: El }) {
  const st = useStation();
  const { value, info, pending, lock: reason } = useChannel(e.ch);
  const lockCh = useChannel(e.lock);
  const op = useCanOperate();
  const isBool = info?.kind === "bool";
  const open = isBool ? value === true : typeof value === "number" && value > 0.2;
  const locked = !!reason || lockCh.value === "LOCKED";
  const bypass = useBypass();
  const can = isBool && !!info?.writable && op.ok && (!locked || bypass);
  const s = 13;
  const rot = e.orient === "v" ? 90 : 0;
  const pct = !isBool && typeof value === "number" ? Math.max(0, Math.min(100, value)) : null;
  const lp = e.label_pos ?? "right";
  const lx = lp === "left" ? e.x - s - 8 : lp === "right" ? e.x + s + 8 : e.x;
  const ly = lp === "above" ? e.y - s - 8 : lp === "below" ? e.y + s + 18 : e.y + 4;
  const anchor = lp === "left" ? "end" : lp === "right" ? "start" : "middle";
  const title = `${info?.label ?? e.ch}: ${isBool ? (open ? "OPEN" : "CLOSED") : `${fmtValue(value, info)} %`}` +
    (locked ? ` · interlocked, can't ${open ? "close" : "open"}${reason ? `: ${reason}` : ""}` : "") + (isBool && info?.writable ? (can ? " (click to switch)" : ` (${op.reason})`) : "");
  return (
    <g className={cx("dgm-valve", open ? "open" : "closed", locked && "locked", can && "clickable", pending && "pending")}
      onClick={() => can && st.write(e.ch, !open)}>
      <title>{title}</title>
      <circle cx={e.x} cy={e.y} r={s + 8} className="valve-hit" />
      <g transform={`translate(${e.x} ${e.y}) rotate(${rot})`}>
        <path d={`M${-s},${-s * 0.75} L0,0 L${-s},${s * 0.75} Z M${s},${-s * 0.75} L0,0 L${s},${s * 0.75} Z`} className="valve-body" />
        {pct !== null && <rect x={-s} y={s * 0.75 + 4} width={2 * s} height={4} className="valve-track" />}
        {pct !== null && <rect x={-s} y={s * 0.75 + 4} width={(2 * s * pct) / 100} height={4} className="valve-pct" />}
      </g>
      {locked && <text x={e.x} y={lp === "above" ? e.y + s + 14 : e.y - s - 4} className="valve-lock" textAnchor="middle">LOCK</text>}
      {e.label && <text x={lx} y={ly} className="dgm-sub" textAnchor={anchor}>{e.label}{pct !== null ? ` ${pct.toFixed(0)}%` : ""}</text>}
    </g>
  );
}

function Gauge({ e }: { e: El }) {
  return (
    <g className="dgm-gauge">
      <circle cx={e.x} cy={e.y} r={17} className="gauge-bubble" />
      <text x={e.x} y={e.y + 4} className="dgm-tag" textAnchor="middle">{e.tag}</text>
      <ValueText ch={e.ch} x={e.x} y={e.y + 34} size={12} />
    </g>
  );
}

const ORDER: Record<string, number> = { pipe: 0, vessel: 1, equipment: 2, gauge: 3, valve: 4, text: 5 };

export default function DiagramWidget({ item }: WidgetProps) {
  const st = useStation();
  useTopic("catalog");
  const diagrams = st.diagrams;
  const id = item.options?.diagram ?? (diagrams.size === 1 ? [...diagrams.keys()][0] : undefined);
  const dg = id ? diagrams.get(id) : undefined;
  if (!dg) return <Unbound what="a diagram" />;
  const els = [...dg.elements].sort((a, b) => (ORDER[a.kind] ?? 9) - (ORDER[b.kind] ?? 9));
  return (
    <div className="dgm">
      <Title sub="live">{item.title || dg.title}</Title>
      <svg className="dgm-svg" viewBox={`0 0 ${dg.width} ${dg.height}`} preserveAspectRatio="xMidYMid meet">
        {els.map((e, k) => {
          switch (e.kind) {
            case "pipe": return <Pipe key={k} e={e} />;
            case "vessel": return <Vessel key={k} e={e} />;
            case "equipment": return <Equipment key={k} e={e} />;
            case "valve": return <Valve key={k} e={e} />;
            case "gauge": return <Gauge key={k} e={e} />;
            case "text": return <text key={k} x={e.x} y={e.y} fontSize={e.size} textAnchor={e.anchor} className="dgm-note">{e.text}</text>;
            default: return null;
          }
        })}
      </svg>
    </div>
  );
}
