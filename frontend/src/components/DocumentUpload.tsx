import { useState } from "react";
import { api } from "../api/client";

type Props = { onUploaded?: () => void };

export default function DocumentUpload({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setStatus("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<{ document_id: string; message: string }>(
        "/api/documents/upload",
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setStatus(`Uploaded. ${data.message}`);
      setFile(null);
      onUploaded?.();
    } catch (err: unknown) {
      setStatus(String((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Upload failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <input
        type="file"
        accept=".pdf,.docx,.xlsx,.csv"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm"
      />
      <button
        type="submit"
        disabled={!file || loading}
        className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
      >
        {loading ? "Uploading..." : "Upload"}
      </button>
      {status && <p className="text-sm text-gray-600">{status}</p>}
    </form>
  );
}
