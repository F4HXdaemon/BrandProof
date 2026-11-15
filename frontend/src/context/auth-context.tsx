"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User, UserRole } from "@/lib/types";
import { api, setToken, removeToken } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
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
      } catch (err) {
        removeToken();
        setTokenState(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }
    loadCurrentUser();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.auth.login(email, password);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    removeToken();
    setTokenState(null);
    setUser(null);
    router.push("/login");
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
