import { Title, Unbound, Value, type WidgetProps } from "@station/kit";

export default function HelloStationReadout({ item }: WidgetProps) {
  if (!item.bind) return <Unbound />;
  return (
    <div className="stat">
      <Title>{item.title || "Hello Station Readout"}</Title>
      <Value ch={item.bind} className="huge" />
    </div>
  );
}
