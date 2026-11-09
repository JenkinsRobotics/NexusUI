import { Segmented, Title, Unbound, WriterNote, useChannel, type WidgetProps } from "@station/kit";

export default function Mode({ item }: WidgetProps) {
  const { info } = useChannel(item.bind);
  if (!item.bind) return <Unbound what="a writable state" />;
  return (
    <div className="mode-w">
      <Title right={<WriterNote ch={item.bind} />}>{item.title || info?.label || item.bind}</Title>
      <Segmented ch={item.bind} />
    </div>
  );
}
