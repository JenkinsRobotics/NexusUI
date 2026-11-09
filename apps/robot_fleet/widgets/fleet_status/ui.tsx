import { CmdButton, StateChip, Value, type WidgetProps } from "@station/kit";

// An app-specific widget: it knows this app's channel names, so it needs no binding.
const UNITS = [
  { name: "SURVEY ROVER", state: "rover.mission", a: ["Battery", "rover_batt.soc"], b: ["Covered", "rover.coverage"] },
  { name: "DRONE", state: "drone.phase", a: ["Battery", "drone_batt.soc"], b: ["Altitude", "drone.alt"] },
  { name: "ROV", state: "sub.phase", a: ["Depth", "sub.depth"], b: ["Tether", "sub.tether"] },
  { name: "TENDER", state: "boat.mode", a: ["Battery", "boat_batt.soc"], b: ["Speed", "boat.speed"] },
];

const CSS = `
.fleet { display: flex; gap: 10px; height: 100%; align-items: stretch; }
.fleet-cell { flex: 1; min-width: 0; background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
  padding: 7px 12px; display: flex; flex-direction: column; justify-content: center; gap: 5px; }
.fleet-head { display: flex; align-items: center; justify-content: space-between; gap: 8px;
  font-size: 10.5px; font-weight: 700; letter-spacing: .09em; color: var(--text-2); }
.fleet-vals { display: flex; gap: 14px; font-size: 11px; color: var(--text-3); white-space: nowrap; }
.fleet-vals .readout { font-size: 12.5px; }
.fleet-stop { flex: 0 0 150px; }
`;

export default function FleetStatus(_: WidgetProps) {
  return (
    <div className="fleet">
      <style>{CSS}</style>
      {UNITS.map((u) => (
        <div className="fleet-cell" key={u.name}>
          <div className="fleet-head"><span>{u.name}</span><StateChip ch={u.state} /></div>
          <div className="fleet-vals">
            <span>{u.a[0]} <Value ch={u.a[1]} /></span>
            <span>{u.b[0]} <Value ch={u.b[1]} /></span>
          </div>
        </div>
      ))}
      <CmdButton cmd="fleet.stop_all" label="STOP ALL" big className="fleet-stop" />
    </div>
  );
}
