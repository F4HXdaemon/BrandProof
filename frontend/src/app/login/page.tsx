"use client";

import React, { useState } from "react";
import Link from "next/link";
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
  const { login, quickSwitchDemoUser, isLoading } = useAuth();
  const { error } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const emailParam = params.get("email");
      if (emailParam) {
        setEmail(emailParam);
      }
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err: any) {
      let msg = err.message || "Invalid credentials";
      if (err.status === 401) {
        msg = "Incorrect email or password. Please check your credentials or create an account.";
      } else if (err.status === 429) {
        msg = "Too many failed attempts. Please wait a few minutes before trying again.";
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

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder={isDemoEnabled ? "name@northstarcloud.com" : "you@company.com"}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="••••••••"
            />
          </div>

          <Button type="submit" className="w-full" isLoading={submitting || isLoading}>
            Sign in
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
                      onClick={() => setEmail(roleEmailMap[u.role] || "")}
                      className="flex w-full items-center justify-between py-2.5 text-left text-sm transition-colors hover:text-accent-ink"
                    >
                      <span>{u.name}</span>
                      <span className="text-xs text-ink-mute">{u.role}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
