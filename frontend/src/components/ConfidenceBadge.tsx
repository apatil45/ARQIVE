type Props = { confidence: string; reason?: string };

const colors: Record<string, string> = {
  HIGH: "bg-green-100 text-green-800",
  MEDIUM: "bg-yellow-100 text-yellow-800",
  LOW: "bg-red-100 text-red-800",
};

export default function ConfidenceBadge({ confidence, reason }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[confidence] || "bg-gray-100"}`}>
        {confidence}
      </span>
      {reason && <span className="text-xs text-gray-500">{reason}</span>}
    </div>
  );
}
