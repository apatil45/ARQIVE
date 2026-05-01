import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* ignore */
    }
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-4 py-2 flex items-center justify-between">
        <div className="flex gap-4">
          <Link to="/" className="font-semibold text-gray-800">ARQIVE</Link>
          <Link to="/search" className="text-gray-600 hover:text-gray-800">Search</Link>
          <Link to="/documents" className="text-gray-600 hover:text-gray-800">Documents</Link>
          {(user?.role === "admin") && (
            <Link to="/admin" className="text-gray-600 hover:text-gray-800">Admin</Link>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{user?.email}</span>
          <button onClick={handleLogout} className="text-sm text-blue-600 hover:underline">Log out</button>
        </div>
      </nav>
      <main className="p-4">{children}</main>
    </div>
  );
}
