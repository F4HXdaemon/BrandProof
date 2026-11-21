"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Building2,
  CheckCircle2,
  AlertCircle,
  Shield,
  Loader2,
  ArrowRight,
  LogOut,
  UserPlus,
  LogIn,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { InviteInfo } from "@/lib/types";
import { Button } from "@/components/ui/button";

export default function AcceptInvitePage() {
  const params = useParams();
  const router = useRouter();
  const token = params?.token as string;

  const { user, isAuthenticated, acceptInvitation, logout, register, login } = useAuth();
  const { success, error } = useToast();

  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAccepting, setIsAccepting] = useState(false);

  // Unauthenticated tab state ("register" | "login")
  const [authMode, setAuthMode] = useState<"register" | "login">("register");

  // Registration form
  const [regFullName, setRegFullName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regSubmitting, setRegSubmitting] = useState(false);

  // Login form
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginSubmitting, setLoginSubmitting] = useState(false);

  useEffect(() => {
    async function verify() {
      if (!token) {
        setErrorMessage("Missing invitation token.");
        setLoading(false);
        return;
      }
      try {
        const info = await api.organizations.validateInvite(token);
        if (!info || !info.valid) {
          setErrorMessage("This invitation is invalid or has expired.");
        } else {
          setInvite(info);
          if (info.email) {
            setRegEmail(info.email);
            setLoginEmail(info.email);
          }
        }
      } catch (err: any) {
        setErrorMessage(
          err.message || "Failed to verify invitation. It may have expired or been revoked."
        );
      } finally {
        setLoading(false);
      }
    }
    verify();
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;
    setIsAccepting(true);
    try {
      const res = await api.organizations.joinWithInvite({ code: token });
      if (res.status === "active") {
        success("Invitation Accepted", `You are now a member of ${invite?.organization_name}!`);
        router.push("/dashboard");
      } else {
        success(
          "Request Submitted",
          "Your membership request has been submitted for administrator approval."
        );
        router.push("/onboarding");
      }
    } catch (err: any) {
      error("Could not accept invitation", err.message || "An error occurred");
    } finally {
      setIsAccepting(false);
    }
  };

  const handleRegisterAndAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regFullName.trim() || !regEmail.trim() || !regPassword) {
      error("Missing fields", "Please fill in all required fields.");
      return;
    }
    setRegSubmitting(true);
    try {
      await register({
        full_name: regFullName.trim(),
        email: regEmail.trim().toLowerCase(),
        password: regPassword,
        invite_token: token,
      });
      success("Account Created & Joined", `Welcome to ${invite?.organization_name}!`);
    } catch (err: any) {
      error("Registration failed", err.message || "Please check your details and try again.");
    } finally {
      setRegSubmitting(false);
    }
  };

  const handleLoginAndAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword) {
      error("Missing fields", "Please enter your email and password.");
      return;
    }
    setLoginSubmitting(true);
    try {
      await login(loginEmail.trim().toLowerCase(), loginPassword);
      // After login completes, accept the invitation
      await acceptInvitation(token);
      success("Signed In & Joined", `Welcome to ${invite?.organization_name}!`);
      router.push("/dashboard");
    } catch (err: any) {
      error("Sign-in failed", err.message || "Incorrect email or password.");
    } finally {
      setLoginSubmitting(false);
    }
  };

  const isEmailMismatch =
    isAuthenticated &&
    user &&
    invite?.email &&
    user.email.toLowerCase() !== invite.email.toLowerCase();

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <Link href="/" className="font-serif text-3xl font-medium tracking-tight text-ink">
            BrandProof
          </Link>
          <p className="text-xs text-ink-mute mt-1 font-mono uppercase tracking-widest">
            Multi-Tenant Brand Integrity & Governance
          </p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="rounded-xl border border-line bg-surface p-8 shadow-soft text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-accent-ink mb-3" />
            <p className="text-sm font-medium text-ink">Verifying invitation...</p>
            <p className="text-xs text-ink-soft mt-1">Checking workspace credentials and role</p>
          </div>
        )}

        {/* Error State */}
        {!loading && errorMessage && (
          <div className="rounded-xl border border-line bg-surface p-8 shadow-soft text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-serif font-medium text-ink">Invitation Unavailable</h2>
            <p className="text-xs text-ink-soft mt-2">{errorMessage}</p>
            <div className="mt-6 flex flex-col gap-2">
              <Link
                href="/login"
                className="w-full inline-flex items-center justify-center rounded-md bg-accent px-4 py-2 text-xs font-medium text-ink hover:bg-accent-hover transition-colors"
              >
                Sign in to BrandProof
              </Link>
              <Link
                href="/dashboard"
                className="text-xs text-ink-soft hover:text-ink transition-colors"
              >
                Return to Dashboard
              </Link>
            </div>
          </div>
        )}

        {/* Valid Invitation Flow */}
        {!loading && invite && (
          <div className="rounded-xl border border-line bg-surface shadow-soft overflow-hidden">
            {/* Invite Banner */}
            <div className="bg-sunken px-6 py-5 border-b border-line text-center">
              <div className="w-12 h-12 rounded-full bg-accent-soft text-accent-ink border border-accent/20 flex items-center justify-center mx-auto mb-3">
                <Building2 className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-serif font-medium text-ink">
                You&apos;ve Been Invited
              </h2>
              <p className="text-xs text-ink-soft mt-1">
                to collaborate on{" "}
                <span className="font-semibold text-ink">{invite.organization_name}</span>
              </p>
              <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 border border-line text-xs">
                <Shield className="w-3.5 h-3.5 text-accent-ink" />
                <span className="text-ink-soft">Assigned Role:</span>
                <span className="font-semibold text-accent-ink">{invite.role || "Reviewer"}</span>
              </div>
            </div>

            <div className="p-6">
              {/* Authenticated State */}
              {isAuthenticated && user ? (
                <div className="space-y-4">
                  {isEmailMismatch ? (
                    <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3.5 text-xs text-ink space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-yellow-700">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>Email Mismatch</span>
                      </div>
                      <p className="text-[11px] text-ink-soft">
                        This invitation was designated for{" "}
                        <strong className="text-ink font-mono">{invite.email}</strong>, but you are
                        currently signed in as{" "}
                        <strong className="text-ink font-mono">{user.email}</strong>.
                      </p>
                      <button
                        type="button"
                        onClick={() => logout()}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-accent-ink hover:underline pt-1"
                      >
                        <LogOut className="w-3 h-3" />
                        Sign out and switch accounts
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div className="rounded-lg border border-accent/20 bg-accent-soft/40 p-3 text-xs text-ink mb-4">
                        <p className="text-ink-soft">
                          Signed in as <strong className="text-ink">{user.full_name}</strong> (
                          {user.email}).
                        </p>
                        <p className="text-[11px] text-ink-mute mt-1">
                          Accepting this invitation will grant you access to{" "}
                          <strong>{invite.organization_name}</strong> while keeping all your existing
                          workspace memberships intact.
                        </p>
                      </div>

                      <Button
                        onClick={handleAccept}
                        disabled={isAccepting}
                        className="w-full flex items-center justify-center gap-2 py-2.5 text-xs font-medium"
                      >
                        {isAccepting ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4" />
                        )}
                        {isAccepting ? "Joining Workspace…" : `Accept & Join ${invite.organization_name}`}
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                /* Unauthenticated State: Sign In or Register */
                <div>
                  {/* Mode Tabs */}
                  <div className="grid grid-cols-2 gap-1 rounded-lg bg-sunken p-1 mb-5">
                    <button
                      type="button"
                      onClick={() => setAuthMode("register")}
                      className={`rounded-md py-1.5 text-xs font-medium transition-colors ${
                        authMode === "register"
                          ? "bg-surface text-ink shadow-sm"
                          : "text-ink-soft hover:text-ink"
                      }`}
                    >
                      New User (Register)
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthMode("login")}
                      className={`rounded-md py-1.5 text-xs font-medium transition-colors ${
                        authMode === "login"
                          ? "bg-surface text-ink shadow-sm"
                          : "text-ink-soft hover:text-ink"
                      }`}
                    >
                      Existing User (Sign In)
                    </button>
                  </div>

                  {authMode === "register" ? (
                    <form onSubmit={handleRegisterAndAccept} className="space-y-3 text-xs">
                      <div>
                        <label className="block font-medium text-ink">Full Name *</label>
                        <input
                          type="text"
                          required
                          placeholder="Julian Chen"
                          value={regFullName}
                          onChange={(e) => setRegFullName(e.target.value)}
                          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                        />
                      </div>

                      <div>
                        <label className="block font-medium text-ink">Email Address *</label>
                        <input
                          type="email"
                          required
                          value={regEmail}
                          disabled={!!invite.email}
                          onChange={(e) => setRegEmail(e.target.value)}
                          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink disabled:bg-sunken disabled:text-ink-mute focus:outline-none focus:border-accent"
                        />
                      </div>

                      <div>
                        <label className="block font-medium text-ink">Password *</label>
                        <input
                          type="password"
                          required
                          placeholder="••••••••"
                          value={regPassword}
                          onChange={(e) => setRegPassword(e.target.value)}
                          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                        />
                      </div>

                      <Button
                        type="submit"
                        disabled={regSubmitting}
                        className="w-full mt-2 flex items-center justify-center gap-1.5 text-xs font-medium py-2.5"
                      >
                        {regSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        Create Account & Join
                      </Button>
                    </form>
                  ) : (
                    <form onSubmit={handleLoginAndAccept} className="space-y-3 text-xs">
                      <div>
                        <label className="block font-medium text-ink">Email Address *</label>
                        <input
                          type="email"
                          required
                          value={loginEmail}
                          onChange={(e) => setLoginEmail(e.target.value)}
                          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                        />
                      </div>

                      <div>
                        <label className="block font-medium text-ink">Password *</label>
                        <input
                          type="password"
                          required
                          placeholder="••••••••"
                          value={loginPassword}
                          onChange={(e) => setLoginPassword(e.target.value)}
                          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                        />
                      </div>

                      <Button
                        type="submit"
                        disabled={loginSubmitting}
                        className="w-full mt-2 flex items-center justify-center gap-1.5 text-xs font-medium py-2.5"
                      >
                        {loginSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        Sign In & Join Workspace
                      </Button>
                    </form>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
