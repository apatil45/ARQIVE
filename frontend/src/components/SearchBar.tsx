import { useState } from "react";

type Props = {
  onSearch: (q: string) => void;
  disabled?: boolean;
};

export default function SearchBar({ onSearch, disabled }: Props) {
  const [q, setQ] = useState("");

  return (
    <div className="flex gap-2 w-full max-w-2xl">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSearch(q)}
        placeholder="Ask about your documents..."
        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        disabled={disabled}
      />
      <button
        type="button"
        onClick={() => onSearch(q)}
        disabled={disabled || !q.trim()}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Search
      </button>
    </div>
  );
}
