import type { Citation } from "../api/client";

type Props = { citation: Citation };

export default function CitationCard({ citation }: Props) {
  return (
    <div className="p-3 border border-gray-200 rounded-lg bg-white text-sm">
      <div className="font-medium text-gray-700">
        {citation.filename} — page {citation.page}
      </div>
      <p className="mt-1 text-gray-600 line-clamp-2">{citation.excerpt}</p>
    </div>
  );
}
