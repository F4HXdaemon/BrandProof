"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, AlertCircle, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { Button } from "@/components/ui/button";
import { UserRole } from "@/lib/types";

const demoUsers: { role: UserRole; name: string }[] = [
  { role: "Reviewer", name: "Julian Chen" },
  { role: "Brand Manager", name: "Marcus Sterling" },
  { role: "Fact Owner", name: "Elena Rostova" },
  { role: "Creator", name: "Samantha Reed" },
  { role: "Admin", name: "Alexandra Vance" },
];

const inputClass =
  "mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";

const isDemoEnabled = process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE === "true";

export default function LoginPage() {
  const router = useRouter();
  const { login, quickSwitchDemoUser, isLoading, isAuthenticated } = useAuth();
  const { error } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(false);
  const [redirectPath, setRedirectPath] = useState<string>("/dashboard");

  useEffect(() => {
    // If the user has a verified, confirmed active session and wasn't sent here due to expiration,
    // seamlessly transition to the intended destination or dashboard.
    if (isAuthenticated && !sessionExpiredNotice) {
      router.replace(redirectPath || "/dashboard");
    }
  }, [isAuthenticated, sessionExpiredNotice, redirectPath, router]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const emailParam = params.get("email");
      if (emailParam) {
        setEmail(emailParam);
      }
      if (params.get("expired") === "true") {
        setSessionExpiredNotice(true);
      }
      const redirectParam = params.get("redirect");
      if (
        redirectParam &&
        redirectParam.startsWith("/") &&
        !redirectParam.startsWith("//") &&
        !redirectParam.startsWith("/login")
      ) {
        setRedirectPath(redirectParam);
      }
    }
  }, []);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      errors.email = "Email address is required.";
    } else if (!emailRegex.test(email.trim())) {
      errors.email = "Please enter a valid email address.";
    }

    if (!password) {
      errors.password = "Password is required.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    try {
      await login(email.trim().toLowerCase(), password, redirectPath);
    } catch (err: any) {
      let msg = "Invalid email or password.";
      if (err.status === 401) {
        msg = "Incorrect email or password. Please verify your credentials or create a new account.";
      } else if (err.status === 429) {
        msg = "Too many login attempts. Please wait a few minutes before trying again.";
      } else if (err.status === 403) {
        msg = "Your account has been deactivated. Please contact your organization administrator.";
      } else if (err.message && !err.message.includes("status 500")) {
        msg = err.message;
      }
      error("Sign in failed", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="font-serif text-2xl font-medium tracking-tight">
          BrandProof
        </Link>
        <h1 className="page-title mt-8 text-3xl">Sign in</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Verify every marketing claim against approved brand evidence.
        </p>

        {sessionExpiredNotice && (
          <div className="mt-4 flex items-center gap-2.5 rounded-md border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-700" />
            <span>Your session has expired. Please sign in again to continue.</span>
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: "" }));
              }}
              className={inputClass}
              placeholder={isDemoEnabled ? "name@northstarcloud.com" : "you@company.com"}
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
            </div>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: "" }));
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
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {fieldErrors.password && (
              <p className="mt-1 text-xs text-rose-500">{fieldErrors.password}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={submitting || isLoading}
            disabled={submitting || isLoading}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="mt-4 text-center text-sm text-ink-soft">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-accent-ink hover:underline">
            Sign up
          </Link>
        </div>

        {!isDemoEnabled && (
          <div className="mt-8 rounded-lg border border-line bg-surface p-4 text-xs text-ink-soft">
            <p className="font-medium text-ink">Exploring BrandProof?</p>
            <p className="mt-1 text-ink-mute">
              Create an isolated sandbox organization to test reviews, guidelines, and compliance rules.
            </p>
            <Link
              href="/register?demo=true"
              className="mt-3 inline-flex items-center gap-1 font-semibold text-accent-ink hover:underline"
            >
              <span>Try Demo Sandbox</span>
              <span aria-hidden="true">&rarr;</span>
            </Link>
          </div>
        )}

        {isDemoEnabled && (
          <div className="mt-10 border-t border-line pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Demo accounts</p>
              <span className="text-[10px] uppercase tracking-wider font-semibold text-accent-ink bg-accent-soft px-2 py-0.5 rounded">
                Demo Environment
              </span>
            </div>
            <ul className="mt-3 divide-y divide-line border-y border-line">
              {demoUsers.map((u) => {
                const roleEmailMap: Record<UserRole, string> = {
                  Owner: "admin@northstarcloud.com",
                  Admin: "admin@northstarcloud.com",
                  "Brand Manager": "brandmanager@northstarcloud.com",
                  "Fact Owner": "factowner@northstarcloud.com",
                  Reviewer: "reviewer@northstarcloud.com",
                  Creator: "creator@northstarcloud.com",
                };
                return (
                  <li key={u.role}>
                    <button
                      type="button"
                      onClick={() => {
                        setEmail(roleEmailMap[u.role] || "");
                        setPassword("BrandProof123!");
                      }}
                      className="flex w-full items-center justify-between py-2.5 text-left text-sm transition-colors hover:text-accent-ink"
                    >
                      <span>{u.name}</span>
                      <span className="text-xs text-ink-mute">{u.role}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2.5 text-center text-xs text-ink-mute">
              Click any demo account above to autofill (password: <span className="font-mono text-ink font-semibold">BrandProof123!</span>)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

