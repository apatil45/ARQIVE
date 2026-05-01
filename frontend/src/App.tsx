import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Index from "./pages/Index";
import Search from "./pages/Search";
import Documents from "./pages/Documents";
import Admin from "./pages/Admin";
import { useAuthStore } from "./stores/auth";

const queryClient = new QueryClient();

function Protected({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore();
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  if (!user) return <div className="p-4">Loading...</div>;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Index /></Protected>} />
          <Route path="/search" element={<Protected><Search /></Protected>} />
          <Route path="/documents" element={<Protected><Documents /></Protected>} />
          <Route path="/admin" element={<Protected><Admin /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
