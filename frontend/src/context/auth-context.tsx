"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User, UserRole, RegisterPayload } from "@/lib/types";
import { api, setToken, removeToken } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string, redirectUrl?: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  quickSwitchDemoUser: (role: UserRole) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    async function loadCurrentUser() {
      const storedToken = typeof window !== "undefined" ? localStorage.getItem("brandproof_token") : null;
      if (!storedToken) {
        setIsLoading(false);
        return;
      }
      try {
        setTokenState(storedToken);
        const me = await api.auth.getMe();
        setUser(me);
      } catch (err: any) {
        // Only discard stored token if explicitly rejected by server (401/403)
        // Network errors or backend spin-up delays should not immediately log the user out
        if (err?.status === 401 || err?.status === 403) {
          removeToken();
          setTokenState(null);
          setUser(null);
        } else {
          console.warn("Backend auth check pending or unreachable:", err?.message || err);
        }
      } finally {
        setIsLoading(false);
      }
    }
    loadCurrentUser();
  }, []);

  const login = async (email: string, password: string, redirectUrl?: string) => {
    setIsLoading(true);
    try {
      const res = await api.auth.login(email, password);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      const target = redirectUrl && redirectUrl.startsWith("/") && !redirectUrl.startsWith("//")
        ? redirectUrl
        : "/dashboard";
      router.push(target);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload) => {
    setIsLoading(true);
    try {
      const res = await api.auth.register(payload);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      // Guide newly registered users directly through the first-time onboarding experience
      router.push("/onboarding");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      removeToken();
      setTokenState(null);
      setUser(null);
      router.push("/login");
    }
  };

  const quickSwitchDemoUser = async (role: UserRole) => {
    const roleEmailMap: Record<UserRole, string> = {
      Admin: "admin@northstarcloud.com",
      "Brand Manager": "brandmanager@northstarcloud.com",
      "Fact Owner": "factowner@northstarcloud.com",
      Reviewer: "reviewer@northstarcloud.com",
      Creator: "creator@northstarcloud.com",
    };
    const email = roleEmailMap[role];
    if (email) {
      removeToken();
      setTokenState(null);
      setUser(null);
      router.push(`/login?email=${encodeURIComponent(email)}`);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        quickSwitchDemoUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
