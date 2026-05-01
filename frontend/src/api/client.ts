import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config;
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true;
      try {
        const { data } = await axios.post(
          `${API_URL}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );
        localStorage.setItem("access_token", data.access_token);
        orig.headers.Authorization = `Bearer ${data.access_token}`;
        return api(orig);
      } catch {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user_id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: string;
};

export type MeResponse = {
  user_id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: string;
};

export type DocumentItem = {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  chunk_count: number;
  created_at: string;
  category?: string;
  doc_date?: string;
};

export type Citation = {
  doc_id: string;
  filename: string;
  page: number;
  excerpt: string;
};

export type QueryResponse = {
  answer: string;
  citations: Citation[];
  confidence: string;
  confidence_reason: string;
  unanswered_aspects?: string | null;
};
