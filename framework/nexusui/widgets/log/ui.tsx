import { Title, clock, useStation, useTopic, type WidgetProps } from "@station/kit";

const RANK: Record<string, number> = { info: 0, warn: 1, alarm: 2 };

export default function Log({ item }: WidgetProps) {
  const st = useStation();
  useTopic("logs");
  const min = RANK[item.options?.level ?? "all"] ?? 0;
  const rows = st.logs.filter((l) => (RANK[l.level] ?? 0) >= min).slice(-200).reverse();
  return (
    <div className="log-w">
      <Title sub={`${rows.length}`}>{item.title || "Event Log"}</Title>
      <div className="log-list">
        {rows.map((l, k) => (
          <div key={`${l.ts}-${k}`} className={`log-row lvl-${l.level}`}>
            <span className="log-time">{clock(l.ts)}</span>
            <span className="log-src">{l.source}</span>
            <span className="log-msg">{l.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
