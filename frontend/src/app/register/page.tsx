"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Sparkles, ArrowRight, ShieldCheck, Eye, EyeOff, Building2, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { InviteInfo } from "@/lib/types";

const inputClass =
  "mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";

export default function RegisterPage() {
  const { register, isLoading } = useAuth();
  const { success, error } = useToast();

  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [inviteToken, setInviteToken] = useState<string>("");
  const [verifiedInvite, setVerifiedInvite] = useState<InviteInfo | null>(null);
  const [verifyingInvite, setVerifyingInvite] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isDemoMode, setIsDemoMode] = useState(false);

  // Generate unique demo credentials for sandbox exploration
  const populateDemoCredentials = () => {
    const randomSuffix = Math.floor(1000 + Math.random() * 9000);
    const randomUser = Math.random().toString(36).substring(2, 7);
    setFullName("Demo Reviewer");
    setOrganizationName(`Demo Brand ${randomSuffix}`);
    setEmail(`demo-${randomUser}@brandproof-demo.org`);
    setPassword("DemoProof2026!");
    setIsDemoMode(true);
    setInviteToken("");
    setVerifiedInvite(null);
    setInviteError(null);
    setFieldErrors({});
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("demo") === "true") {
        populateDemoCredentials();
      }
      const token = params.get("invite");
      if (token) {
        setInviteToken(token);
        verifyInviteToken(token);
      }
    }
  }, []);

  const verifyInviteToken = async (token: string) => {
    setVerifyingInvite(true);
    setInviteError(null);
    try {
      const info = await api.auth.verifyInvite(token);
      if (!info || !info.valid) {
        setVerifiedInvite(null);
        setInviteError("This invitation is invalid or has expired.");
      } else {
        setVerifiedInvite(info);
        if (info.email) {
          setEmail(info.email);
        }
      }
    } catch (err: any) {
      setVerifiedInvite(null);
      setInviteError(err.message || "This invitation link is invalid or expired.");
    } finally {
      setVerifyingInvite(false);
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!fullName.trim() || fullName.trim().length < 2) {
      errors.fullName = "Full name must be at least 2 characters.";
    }

    // Organization name is required ONLY when intentionally creating a new org (not invitation mode)
    if (!inviteToken && (!organizationName.trim() || organizationName.trim().length < 2)) {
      errors.organizationName = "Organization name must be at least 2 characters.";
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim() || !emailRegex.test(email.trim())) {
      errors.email = "Please enter a valid email address.";
    }

    if (!password || password.length < 8) {
      errors.password = "Password must be at least 8 characters.";
    } else if (new TextEncoder().encode(password).length > 72) {
      errors.password = "Password must not exceed 72 bytes.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // If in invitation mode, require a verified invitation
    if (inviteToken && !verifiedInvite) {
      error("Invitation Verification Required", "Please resolve the invitation issue or choose to create a new organization.");
      return;
    }

    if (!validate()) return;

    setSubmitting(true);
    try {
      await register({
        full_name: fullName.trim(),
        organization_name: verifiedInvite ? undefined : organizationName.trim(),
        email: email.trim().toLowerCase(),
        password,
        invite_token: verifiedInvite ? inviteToken : undefined,
      });
      success(
        "Account Created",
        `Welcome to BrandProof, ${fullName.trim()}! Let's get you set up.`
      );
    } catch (err: any) {
      let message = err.message || "Registration failed. Please check your inputs.";
      if (err.status === 400 && message.toLowerCase().includes("email")) {
        setFieldErrors((prev) => ({ ...prev, email: "An account with this email address already exists." }));
        message = "A user with this email address already exists. Please sign in or use another email.";
      } else if (err.status === 409) {
        setFieldErrors((prev) => ({
          ...prev,
          organizationName: "An organization with this name/slug already exists.",
        }));
        message = "An organization with this slug already exists. Please choose a unique name.";
      } else if (err.status === 429) {
        message = "Too many registration attempts. Please wait a few moments before trying again.";
      }
      error("Registration Failed", message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSwitchToCreateOrg = () => {
    setInviteToken("");
    setVerifiedInvite(null);
    setInviteError(null);
    setFieldErrors({});
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("invite");
      window.history.replaceState({}, "", url.pathname);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <Link href="/" className="font-serif text-2xl font-medium tracking-tight">
          BrandProof
        </Link>
        <h1 className="page-title mt-6 text-3xl">
          {inviteToken ? "Join team workspace" : "Create your organization"}
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          {inviteToken
            ? verifiedInvite
              ? `Accept your invitation to collaborate on ${verifiedInvite.organization_name}.`
              : "Verifying your workspace invitation..."
            : "Start verifying drafts against approved brand facts, guidelines, and rules."}
        </p>

        {/* Verifying Invitation Loader */}
        {verifyingInvite && (
          <div className="mt-6 rounded-lg border border-line bg-surface p-4 text-xs text-ink flex items-center gap-3">
            <Loader2 className="w-4 h-4 animate-spin text-accent-ink shrink-0" />
            <span>Verifying invitation credentials with the server...</span>
          </div>
        )}

        {/* Invalid Invitation Error Banner (DOES NOT SILENTLY FALL BACK) */}
        {!verifyingInvite && inviteError && (
          <div className="mt-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-xs text-ink space-y-3">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-red-600">Invalid or Expired Invitation</p>
                <p className="text-ink-soft mt-1">{inviteError}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 pt-2 border-t border-red-500/20">
              <Link href="/login" className="font-medium text-accent-ink hover:underline">
                Sign in to existing account
              </Link>
              <span className="text-ink-mute">·</span>
              <button
                type="button"
                onClick={handleSwitchToCreateOrg}
                className="font-medium text-ink hover:underline"
              >
                Create a new organization instead
              </button>
            </div>
          </div>
        )}

        {/* Verified Invitation Banner */}
        {!verifyingInvite && verifiedInvite && (
          <div className="mt-6 rounded-lg border border-accent/40 bg-accent-soft p-3.5 text-xs text-ink flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-accent-ink shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-ink">
                Verified invitation to join <span className="underline">{verifiedInvite.organization_name}</span>
              </p>
              <p className="text-ink-soft mt-0.5">
                You will join as <strong>{verifiedInvite.role || "Member"}</strong>. In accordance with security policy, roles are assigned by workspace administrators.
              </p>
            </div>
          </div>
        )}

        {/* Quick Demo Sandbox Option (only when not in invite mode) */}
        {!inviteToken && (
          <div className="mt-6 rounded-lg border border-accent/30 bg-accent-soft p-3.5 text-xs text-ink flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <Sparkles className="w-4 h-4 text-accent-ink shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-ink">Want to quickly explore?</p>
                <p className="text-ink-soft mt-0.5">
                  Generate sample sandbox details to test the review pipeline with zero setup.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={populateDemoCredentials}
              className="shrink-0 font-semibold text-accent-ink hover:underline inline-flex items-center gap-1"
            >
              {isDemoMode ? "Regenerate" : "Fill Sample"}
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* Form is only rendered if not blocked by an unverified invite */}
        {(!inviteToken || verifiedInvite) && (
          <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
            {/* Organization Name Field (only if creating a new org) */}
            {!verifiedInvite && (
              <div>
                <label htmlFor="organizationName" className="block text-sm font-medium">
                  Organization name
                </label>
                <input
                  id="organizationName"
                  type="text"
                  required
                  value={organizationName}
                  onChange={(e) => {
                    setOrganizationName(e.target.value);
                    if (fieldErrors.organizationName) {
                      setFieldErrors((prev) => ({ ...prev, organizationName: "" }));
                    }
                  }}
                  className={inputClass}
                  placeholder="e.g. Acme Corp"
                />
                {fieldErrors.organizationName && (
                  <p className="mt-1 text-xs text-rose-500">{fieldErrors.organizationName}</p>
                )}
                <p className="mt-1 text-[11px] text-ink-mute">
                  Creates a dedicated, isolated governance workspace for your brand.
                </p>
              </div>
            )}

            <div>
              <label htmlFor="fullName" className="block text-sm font-medium">
                Your full name
              </label>
              <input
                id="fullName"
                type="text"
                required
                autoComplete="name"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (fieldErrors.fullName) {
                    setFieldErrors((prev) => ({ ...prev, fullName: "" }));
                  }
                }}
                className={inputClass}
                placeholder="e.g. Alexandra Vance"
              />
              {fieldErrors.fullName && (
                <p className="mt-1 text-xs text-rose-500">{fieldErrors.fullName}</p>
              )}
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium">
                Work email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                disabled={!!verifiedInvite?.email}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email) {
                    setFieldErrors((prev) => ({ ...prev, email: "" }));
                  }
                }}
                className={`${inputClass} ${verifiedInvite?.email ? "bg-sunken cursor-not-allowed" : ""}`}
                placeholder="you@company.com"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-rose-500">{fieldErrors.email}</p>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="block text-sm font-medium">
                  Password
                </label>
                <span className="text-[11px] text-ink-mute">Min 8 characters</span>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) {
                      setFieldErrors((prev) => ({ ...prev, password: "" }));
                    }
                  }}
                  className={`${inputClass} pr-10`}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-mute hover:text-ink transition-colors p-1"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password ? (
                <p className="mt-1 text-xs text-rose-500">{fieldErrors.password}</p>
              ) : (
                <p className="mt-1 text-[11px] text-ink-mute">
                  Passwords are never stored in plaintext and are hashed using bcrypt.
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full mt-2"
              isLoading={submitting || isLoading || verifyingInvite}
              disabled={submitting || isLoading || verifyingInvite}
            >
              {submitting ? "Creating account…" : verifiedInvite ? "Accept & Join Workspace" : "Create Organization & Account"}
            </Button>
          </form>
        )}

        <div className="mt-6 text-center text-sm text-ink-soft">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent-ink hover:underline">
            Sign in
          </Link>
        </div>

        <div className="mt-8 border-t border-line pt-6 flex items-center justify-center gap-2 text-xs text-ink-mute">
          <ShieldCheck className="w-3.5 h-3.5 text-accent-ink" />
          <span>Strict isolation. AI proposes. Humans approve.</span>
        </div>
      </div>
    </div>
  );
}
