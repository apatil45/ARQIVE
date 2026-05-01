import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { MeResponse } from "../api/client";

type AuthState = {
  user: MeResponse | null;
  setUser: (u: MeResponse | null) => void;
  setToken: (token: string) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      setToken: (token) => {
        localStorage.setItem("access_token", token);
      },
      logout: () => {
        localStorage.removeItem("access_token");
        set({ user: null });
      },
    }),
    { name: "arqive-auth", partialize: (s) => ({ user: s.user }) }
  )
);
