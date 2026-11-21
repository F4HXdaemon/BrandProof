"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { User, UserRole, UserOrganization, OrganizationInvitation, RegisterPayload } from "@/lib/types";
import { api, setToken, removeToken, setActiveOrgId, getActiveOrgId } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  currentOrganization: UserOrganization | null;
  organizations: UserOrganization[];
  pendingInvitations: OrganizationInvitation[];
  login: (email: string, password: string, redirectUrl?: string, rememberMe?: boolean) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  completeOnboarding: () => Promise<void>;
  quickSwitchDemoUser: (role: UserRole) => Promise<void>;
  switchOrganization: (orgId: string) => Promise<void>;
  createOrganization: (data: { name: string; slug?: string; domain?: string }) => Promise<void>;
  refreshOrganizations: () => Promise<UserOrganization[]>;
  refreshInvitations: () => Promise<OrganizationInvitation[]>;
  acceptInvitation: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [organizations, setOrganizations] = useState<UserOrganization[]>([]);
  const [currentOrganization, setCurrentOrganization] = useState<UserOrganization | null>(null);
  const [pendingInvitations, setPendingInvitations] = useState<OrganizationInvitation[]>([]);
  const router = useRouter();

  const refreshOrganizations = useCallback(async () => {
    try {
      const orgs = await api.organizations.getMyOrganizations();
      setOrganizations(orgs);
      const activeId = getActiveOrgId();
      const curr =
        (activeId ? orgs.find((o) => o.id === activeId) : null) ||
        orgs.find((o) => o.is_current) ||
        orgs[0] ||
        null;
      setCurrentOrganization(curr);
      if (curr) {
        setActiveOrgId(curr.id);
      }
      return orgs;
    } catch (err) {
      console.warn("Failed to load organizations:", err);
      return [];
    }
  }, []);

  const refreshInvitations = useCallback(async () => {
    try {
      const invites = await api.organizations.getMyInvitations();
      setPendingInvitations(invites);
      return invites;
    } catch (err) {
      console.warn("Failed to load pending invitations:", err);
      return [];
    }
  }, []);

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
        await Promise.allSettled([refreshOrganizations(), refreshInvitations()]);
      } catch (err: any) {
        // Only discard stored token if explicitly rejected by server (401/403)
        // Network errors or backend spin-up delays should not immediately log the user out
        if (err?.status === 401 || err?.status === 403) {
          removeToken();
          setTokenState(null);
          setUser(null);
          setOrganizations([]);
          setCurrentOrganization(null);
          setPendingInvitations([]);
        } else {
          console.warn("Backend auth check pending or unreachable:", err?.message || err);
        }
      } finally {
        setIsLoading(false);
      }
    }
    loadCurrentUser();
  }, [refreshOrganizations, refreshInvitations]);

  const login = async (email: string, password: string, redirectUrl?: string, rememberMe?: boolean) => {
    setIsLoading(true);
    try {
      const res = await api.auth.login(email, password, rememberMe);
      setToken(res.access_token, rememberMe || false);
      setTokenState(res.access_token);
      setUser(res.user);
      setActiveOrgId(res.user.organization_id);

      await Promise.allSettled([refreshOrganizations(), refreshInvitations()]);

      const target =
        redirectUrl && redirectUrl.startsWith("/") && !redirectUrl.startsWith("//")
          ? redirectUrl
          : "/dashboard";
      router.push(target);
    } finally {
      setIsLoading(false);
    }
  };

  const completeOnboarding = useCallback(async () => {
    try {
      const updated = await api.users.updateOnboarding(true);
      setUser(updated);
    } catch (err) {
      console.warn("Failed to update onboarding state:", err);
    }
  }, []);

  const register = async (payload: RegisterPayload) => {
    setIsLoading(true);
    try {
      const res = await api.auth.register(payload);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      setActiveOrgId(res.user.organization_id);

      await Promise.allSettled([refreshOrganizations(), refreshInvitations()]);

      // If registered via invitation, direct to dashboard; otherwise onboarding
      if (payload.invite_token) {
        router.push("/dashboard");
      } else {
        router.push("/onboarding");
      }
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
      setOrganizations([]);
      setCurrentOrganization(null);
      setPendingInvitations([]);
      router.push("/login");
    }
  };

  const switchOrganization = async (orgId: string) => {
    setIsLoading(true);
    try {
      const res = await api.organizations.switchOrganization(orgId);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      setActiveOrgId(res.organization.id);

      const updatedOrgs = await refreshOrganizations();
      const switched = updatedOrgs.find((o) => o.id === res.organization.id);
      if (switched) {
        setCurrentOrganization(switched);
      }
      // Force page refresh to flush caches for all queries across the active route
      if (typeof window !== "undefined") {
        window.location.reload();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const createOrganization = async (data: { name: string; slug?: string; domain?: string }) => {
    setIsLoading(true);
    try {
      const res = await api.organizations.createOrganization(data);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      setActiveOrgId(res.organization.id);

      const updatedOrgs = await refreshOrganizations();
      const created = updatedOrgs.find((o) => o.id === res.organization.id);
      if (created) {
        setCurrentOrganization(created);
      }
      if (typeof window !== "undefined") {
        window.location.reload();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const acceptInvitation = async (invitationToken: string) => {
    setIsLoading(true);
    try {
      const res = await api.organizations.acceptInvitation(invitationToken);
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      setActiveOrgId(res.organization.id);

      await Promise.allSettled([refreshOrganizations(), refreshInvitations()]);
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const quickSwitchDemoUser = async (role: UserRole) => {
    const roleEmailMap: Record<UserRole, string> = {
      Owner: "admin@northstarcloud.com",
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
      setOrganizations([]);
      setCurrentOrganization(null);
      setPendingInvitations([]);
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
        currentOrganization,
        organizations,
        pendingInvitations,
        login,
        register,
        logout,
        completeOnboarding,
        quickSwitchDemoUser,
        switchOrganization,
        createOrganization,
        refreshOrganizations,
        refreshInvitations,
        acceptInvitation,
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
