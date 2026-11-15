"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Sparkles, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { Button } from "@/components/ui/button";

const inputClass =
  "mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";

export default function RegisterPage() {
  const { register, isLoading } = useAuth();
  const { success, error } = useToast();

  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    setFieldErrors({});
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("demo") === "true") {
        populateDemoCredentials();
      }
    }
  }, []);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!fullName.trim() || fullName.trim().length < 2) {
      errors.fullName = "Full name must be at least 2 characters.";
    }

    if (!organizationName.trim() || organizationName.trim().length < 2) {
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
    if (!validate()) return;

    setSubmitting(true);
    try {
      await register({
        full_name: fullName.trim(),
        organization_name: organizationName.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      success(
        "Workspace Created",
        `Welcome to BrandProof, ${fullName.trim()}! Your organization "${organizationName.trim()}" is ready.`
      );
    } catch (err: any) {
      const message = err.message || "Registration failed. Please check your inputs.";
      error("Registration Failed", message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <Link href="/" className="font-serif text-2xl font-medium tracking-tight">
          BrandProof
        </Link>
        <h1 className="page-title mt-6 text-3xl">Create your organization</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Start verifying drafts against approved brand facts, guidelines, and rules.
        </p>

        {/* Quick Demo Sandbox Option */}
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

        <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
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

          <div>
            <label htmlFor="fullName" className="block text-sm font-medium">
              Your full name
            </label>
            <input
              id="fullName"
              type="text"
              required
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
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) {
                  setFieldErrors((prev) => ({ ...prev, email: "" }));
                }
              }}
              className={inputClass}
              placeholder="you@company.com"
            />
            {fieldErrors.email && (
              <p className="mt-1 text-xs text-rose-500">{fieldErrors.email}</p>
            )}
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
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) {
                  setFieldErrors((prev) => ({ ...prev, password: "" }));
                }
              }}
              className={inputClass}
              placeholder="At least 8 characters"
            />
            {fieldErrors.password ? (
              <p className="mt-1 text-xs text-rose-500">{fieldErrors.password}</p>
            ) : (
              <p className="mt-1 text-[11px] text-ink-mute">
                Must be between 8 and 72 characters.
              </p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={submitting || isLoading}
          >
            Create Organization & Account
          </Button>
        </form>

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
