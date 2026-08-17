type Props = {
  value: unknown;
  emptyText?: string;
};

export default function JsonViewer({ value, emptyText = "No data" }: Props) {
  if (!value) {
    return <p className="muted">{emptyText}</p>;
  }

  return <pre className="json-viewer">{JSON.stringify(value, null, 2)}</pre>;
}
