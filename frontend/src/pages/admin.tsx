import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function Admin() {
  const { data: users = [] } = useQuery({
    queryKey: ["admin-users"],
    queryFn: async () => {
      const { data } = await api.get("/api/admin/users");
      return data;
    },
  });
  const { data: audit = { items: [] } } = useQuery({
    queryKey: ["admin-audit"],
    queryFn: async () => {
      const { data } = await api.get("/api/admin/audit-log");
      return data;
    },
  });
  const { data: stats = {} } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      const { data } = await api.get("/api/admin/stats");
      return data;
    },
  });

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-8">
      <h2 className="text-xl font-semibold">Admin</h2>
      <section>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Stats</h3>
        <p className="text-sm">Indexed documents: {stats.indexed_documents ?? 0}</p>
        <p className="text-sm">Total queries: {stats.total_queries ?? 0}</p>
      </section>
      <section>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Users</h3>
        <ul className="space-y-1 text-sm">
          {users.map((u: { email: string; role: string }) => (
            <li key={u.email}>{u.email} — {u.role}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Audit log (recent)</h3>
        <ul className="space-y-1 text-sm">
          {(audit.items ?? []).slice(0, 10).map((a: { action: string; timestamp: string; query_text?: string }) => (
            <li key={a.timestamp}>
              {a.timestamp} — {a.action} {a.query_text ? `"${a.query_text.slice(0, 40)}..."` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
