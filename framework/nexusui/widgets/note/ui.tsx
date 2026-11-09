import { Title, type WidgetProps } from "@station/kit";

export default function Note({ item }: WidgetProps) {
  return (
    <div className="note-w">
      {item.title && <Title>{item.title}</Title>}
      <div className="note-text">{item.options?.text || "Edit the layout to write a note."}</div>
    </div>
  );
}
