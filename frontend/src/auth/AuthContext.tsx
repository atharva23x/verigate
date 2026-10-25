import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";
import { api } from "../api/client";
import type { TokenResponse } from "../types";

interface User {
  username: string;
  role: "officer" | "reviewer" | "auditor";
  full_name: string;
}

interface AuthCtx {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  canReview: boolean; // officer or reviewer
  canUpload: boolean; // officer only
}

const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("verigate_user");
    return raw ? JSON.parse(raw) : null;
  });

  useEffect(() => {
    // Validate the stored token on load; force re-login if it expired.
    if (user) {
      api.get("/auth/me").catch(() => setUser(null));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      async login(username, password) {
        const { data } = await api.post<TokenResponse>("/auth/login", {
          username,
          password,
        });
        localStorage.setItem("verigate_token", data.access_token);
        const u: User = {
          username: data.username,
          role: data.role,
          full_name: data.full_name,
        };
        localStorage.setItem("verigate_user", JSON.stringify(u));
        setUser(u);
      },
      logout() {
        localStorage.removeItem("verigate_token");
        localStorage.removeItem("verigate_user");
        setUser(null);
      },
      canReview: user?.role === "officer" || user?.role === "reviewer",
      canUpload: user?.role === "officer",
    }),
    [user]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(Ctx);
