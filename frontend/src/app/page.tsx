"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck, CheckCircle2, FileSearch, Sparkles } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { UserRole } from "@/lib/types";

const steps = [
  {
    step: "01",
    title: "Check",
    body: "Rule checkers split a draft into individual claims and compare each claim against your approved facts, terminology, and brand guidelines.",
  },
  {
    step: "02",
    title: "Cite",
    body: "A finding is raised only when it can cite a verified fact, rule, or guideline matching the product, region, and channel. No source = no finding.",
  },
  {
    step: "03",
    title: "Approve",
    body: "Human reviewers make the final call. Any blocker prevents publication until resolved or overridden with an audited reason by a brand manager.",
  },
];

const governanceRoles: { role: UserRole; name: string; about: string }[] = [
  { role: "Reviewer", name: "Julian Chen", about: "Triages automated findings, inspects evidence citations, and issues approvals or change requests." },
  { role: "Brand Manager", name: "Marcus Sterling", about: "Curates guidelines, forbidden terms, and policy rules. Has authority to override blockers." },
  { role: "Fact Owner", name: "Elena Rostova", about: "Registers authoritative claims, verified metrics, SLA dates, and evidence URLs." },
  { role: "Creator", name: "Samantha Reed", about: "Submits ad copy, blog posts, and launch drafts to receive instantaneous compliance feedback." },
  { role: "Admin", name: "Alexandra Vance", about: "Manages organizations, member access, rule policies, and the immutable audit trail." },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col">
      {/* Navigation Header */}
      <header className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-6">
        <Link href="/" className="font-serif text-xl font-medium tracking-tight text-ink">
          BrandProof
        </Link>
        {isAuthenticated ? (
          <Link
            href="/dashboard"
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-accent-hover"
          >
            Open dashboard
          </Link>
        ) : (
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm font-medium text-ink-soft hover:text-ink">
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover shadow-sm"
            >
              Sign up
            </Link>
          </div>
        )}
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6">
        {/* Hero Section */}
        <section className="pt-20 pb-20 sm:pt-28 sm:pb-24">
          <div className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink-soft mb-6">
            <ShieldCheck className="w-3.5 h-3.5 text-accent-ink" />
            <span>AI proposes. Evidence decides. People approve.</span>
          </div>

          <h1 className="page-title max-w-3xl text-5xl sm:text-6xl leading-[1.05] text-ink font-serif font-medium tracking-tight">
            Every claim, traced to its source.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-soft">
            BrandProof checks marketing drafts against your approved facts, guidelines, and
            terminology before anything goes live. Every finding cites an authoritative source,
            and human reviewers make the final decision.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/register"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover shadow-sm inline-flex items-center gap-1.5"
            >
              <span>Get Started Free</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/register?demo=true"
              className="rounded-md border border-line-strong bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-sunken inline-flex items-center gap-1.5"
            >
              <Sparkles className="w-4 h-4 text-accent-ink" />
              <span>Try Demo Sandbox</span>
            </Link>
            <Link href="/login" className="text-sm font-medium text-ink-soft hover:text-ink ml-1">
              Sign in &rarr;
            </Link>
          </div>
        </section>

        {/* How It Works Section */}
        <section className="border-t border-line py-16">
          <div className="flex items-center gap-2 mb-2">
            <FileSearch className="w-4 h-4 text-accent-ink" />
            <h2 className="text-xs uppercase tracking-wider font-semibold text-ink-mute">
              How it works
            </h2>
          </div>
          <p className="text-xl font-serif font-medium text-ink">
            A deterministic pipeline backed by evidence.
          </p>

          <div className="mt-8 grid gap-8 md:grid-cols-3">
            {steps.map((s) => (
              <div key={s.title} className="rounded-lg border border-line bg-surface p-5">
                <span className="font-mono text-xs font-semibold text-accent-ink">{s.step}</span>
                <h3 className="mt-2 text-base font-semibold text-ink">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Governance Roles Section */}
        <section className="border-t border-line py-16">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
            <div>
              <h2 className="text-xs uppercase tracking-wider font-semibold text-ink-mute">
                Role-Based Governance
              </h2>
              <p className="mt-1 text-xl font-serif font-medium text-ink">
                Built for collaborative brand safety
              </p>
              <p className="mt-1 text-sm text-ink-soft">
                Each team member operates with tailored permissions and distinct responsibilities.
              </p>
            </div>
            <Link
              href="/register?demo=true"
              className="inline-flex items-center gap-1 text-xs font-medium text-accent-ink hover:underline shrink-0"
            >
              <span>Explore all roles in sandbox</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <ul className="divide-y divide-line border-y border-line">
            {governanceRoles.map((u) => (
              <li key={u.role} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-4">
                <div className="w-56">
                  <p className="text-sm font-medium text-ink">{u.name}</p>
                  <p className="text-xs text-accent-ink font-mono">{u.role}</p>
                </div>
                <p className="flex-1 min-w-[16rem] text-sm text-ink-soft">{u.about}</p>
                <div className="flex items-center gap-3">
                  <Link
                    href={`/login?email=${encodeURIComponent(
                      u.role === "Admin"
                        ? "admin@northstarcloud.com"
                        : u.role === "Brand Manager"
                        ? "brandmanager@northstarcloud.com"
                        : u.role === "Fact Owner"
                        ? "factowner@northstarcloud.com"
                        : u.role === "Reviewer"
                        ? "reviewer@northstarcloud.com"
                        : "creator@northstarcloud.com"
                    )}`}
                    className="text-xs font-medium text-ink-soft hover:text-ink"
                  >
                    Sign in
                  </Link>
                  <span className="text-ink-mute">·</span>
                  <Link
                    href="/register?demo=true"
                    className="text-xs font-medium text-accent-ink hover:underline"
                  >
                    Sandbox
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* CTA Banner */}
        <section className="border-t border-line py-16 text-center">
          <h2 className="font-serif text-3xl font-medium text-ink">
            Ready to protect your brand before content publishes?
          </h2>
          <p className="mt-3 text-sm text-ink-soft max-w-lg mx-auto">
            Create an isolated workspace for your organization or test the platform immediately in sandbox mode.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/register"
              className="rounded-md bg-accent px-6 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover shadow-sm"
            >
              Create Organization
            </Link>
            <Link
              href="/register?demo=true"
              className="rounded-md border border-line-strong bg-surface px-6 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-sunken"
            >
              Try Demo Sandbox
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-line bg-paper">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6 text-xs text-ink-mute">
          <div className="flex items-center gap-2">
            <span className="font-serif font-medium text-ink">BrandProof</span>
            <span>·</span>
            <span>NO VALID SOURCE = NO FINDING</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/register" className="hover:text-ink">
              Sign up
            </Link>
            <Link href="/login" className="hover:text-ink">
              Sign in
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
