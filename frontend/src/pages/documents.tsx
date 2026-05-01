import { useQuery } from "@tanstack/react-query";
import { api, type DocumentItem } from "../api/client";
import DocumentUpload from "../components/DocumentUpload";
import { useAuthStore } from "../stores/auth";

export default function Documents() {
  const { user } = useAuthStore();
  const { data: docs = [], refetch } = useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      const { data } = await api.get<DocumentItem[]>("/api/documents");
      return data;
    },
  });

  const canUpload = user?.role === "auditor" || user?.role === "admin";

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      <h2 className="text-xl font-semibold">Documents</h2>
      {canUpload && (
        <div className="p-4 border rounded-lg bg-gray-50">
          <h3 className="text-sm font-medium mb-2">Upload</h3>
          <DocumentUpload onUploaded={() => refetch()} />
        </div>
      )}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-left p-2">Filename</th>
              <th className="text-left p-2">Type</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Chunks</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} className="border-t">
                <td className="p-2">{d.filename}</td>
                <td className="p-2">{d.file_type}</td>
                <td className="p-2">{d.status}</td>
                <td className="p-2">{d.chunk_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {docs.length === 0 && (
          <p className="p-4 text-gray-500 text-center">No documents yet.</p>
        )}
      </div>
    </div>
  );
}
