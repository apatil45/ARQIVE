import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { LoginResponse } from "../api/client";
import { useAuthStore } from "../stores/auth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setUser, setToken } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post<LoginResponse>("/api/auth/login", {
        email,
        password,
      });
      setToken(data.access_token);
      setUser({
        user_id: data.user_id,
        tenant_id: data.tenant_id,
        email: data.email,
        full_name: data.full_name,
        role: data.role,
      });
      navigate("/");
    } catch (err: unknown) {
      const d = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(d ?? "Login failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">ARQIVE</h1>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2 border rounded mb-3"
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 border rounded mb-4"
          required
        />
        {error && <p className="text-red-600 text-sm mb-2">{error}</p>}
        <button type="submit" className="w-full py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          Log in
        </button>
      </form>
    </div>
  );
}
