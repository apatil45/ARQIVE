import { useState, useCallback } from "react";
import SearchBar from "../components/SearchBar";
import AnswerStream from "../components/AnswerStream";
import CitationCard from "../components/CitationCard";
import ConfidenceBadge from "../components/ConfidenceBadge";
import type { Citation } from "../api/client";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Search() {
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [confidence, setConfidence] = useState("");
  const [confidenceReason, setConfidenceReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    setConfidence("");
    setConfidenceReason("");
    const token = localStorage.getItem("access_token");
    try {
      const url = `${API_URL}/api/query/stream?q=${encodeURIComponent(q)}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(res.statusText);
      const reader = res.body?.getReader();
      const dec = new TextDecoder();
      let buf = "";
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === "token") setAnswer((a) => a + (data.content ?? ""));
                if (data.type === "citations") setCitations(data.data ?? []);
                if (data.type === "confidence") {
                  setConfidence(data.data?.confidence ?? "");
                  setConfidenceReason(data.data?.reason ?? "");
                }
                if (data.type === "error") setError(data.message ?? "Error");
              } catch {}
            }
          }
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      <h2 className="text-xl font-semibold">Search documents</h2>
      <SearchBar onSearch={onSearch} disabled={loading} />
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <AnswerStream content={answer} isStreaming={loading} />
      {(confidence || citations.length > 0) && (
        <div className="space-y-2">
          {confidence && (
            <ConfidenceBadge confidence={confidence} reason={confidenceReason} />
          )}
          {citations.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">Citations</h3>
              <div className="grid gap-2">
                {citations.map((c, i) => (
                  <CitationCard key={i} citation={c} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
