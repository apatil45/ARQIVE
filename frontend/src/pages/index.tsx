import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";
import Search from "./Search";

export default function Index() {
  const navigate = useNavigate();
  const { user, setUser } = useAuthStore();

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      navigate("/login");
      return;
    }
    api.get("/api/auth/me").then(({ data }) => setUser(data)).catch(() => navigate("/login"));
  }, [navigate, setUser]);

  if (!user) return <div className="p-4">Loading...</div>;
  return <Search />;
}
