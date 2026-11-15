"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { UserRole } from "@/lib/types";

const steps = [
  {
    title: "Check",
    body: "Rule checkers split a draft into claims and compare each one with your approved facts, terminology and guidelines.",
  },
  {
    title: "Cite",
    body: "A finding is raised only when it can point to a current fact, rule or guideline that applies to the product, region and channel. No source, no finding.",
  },
  {
    title: "Approve",
    body: "Reviewers decide what ships. An open blocker locks publication until a brand manager overrides it with a written reason, which is kept in the audit log.",
  },
];

const demoUsers: { role: UserRole; name: string; about: string }[] = [
  { role: "Reviewer", name: "Julian Chen", about: "Triages findings, accepts fixes, approves or requests changes." },
  { role: "Brand Manager", name: "Marcus Sterling", about: "Maintains guidelines and terminology. Can override blockers." },
  { role: "Fact Owner", name: "Elena Rostova", about: "Maintains approved facts and their expiry dates." },
  { role: "Creator", name: "Samantha Reed", about: "Submits drafts and reads the feedback." },
  { role: "Admin", name: "Alexandra Vance", about: "Manages rules, team access and the audit log." },
];

export default function LandingPage() {
  const router = useRouter();
  const { isAuthenticated, quickSwitchDemoUser } = useAuth();
  const [pending, setPending] = useState<string | null>(null);

  const enterAs = async (role: UserRole) => {
    setPending(role);
    try {
      await quickSwitchDemoUser(role);
      router.push("/dashboard");
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col">
      <header className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-6">
        <span className="font-serif text-xl font-medium tracking-tight">BrandProof</span>
        {isAuthenticated ? (
          <Link
            href="/dashboard"
            className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover"
          >
            Open dashboard
          </Link>
        ) : (
          <Link href="/login" className="text-sm text-ink-soft hover:text-ink">
            Sign in
          </Link>
        )}
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6">
        {/* Hero */}
        <section className="pt-20 pb-24 sm:pt-28">
          <h1 className="page-title max-w-3xl text-5xl sm:text-6xl leading-[1.05] text-ink">
            Every claim, traced to its source.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-soft">
            BrandProof checks marketing drafts against your approved facts, guidelines and
            terminology before anything is published. Every finding cites a source, and people
            make the final call.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              onClick={() => enterAs("Reviewer")}
              disabled={pending !== null}
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover disabled:opacity-60"
            >
              {pending === "Reviewer" ? "Opening…" : "Try the demo"}
            </button>
            <Link href="/login" className="text-sm text-ink-soft hover:text-ink">
              Sign in with email
            </Link>
          </div>
        </section>

        {/* How it works */}
        <section className="border-t border-line py-16">
          <h2 className="text-sm font-medium text-ink-mute">How it works</h2>
          <div className="mt-8 grid gap-10 md:grid-cols-3">
            {steps.map((s, i) => (
              <div key={s.title}>
                <p className="font-serif text-3xl text-accent-ink">{i + 1}</p>
                <h3 className="mt-3 text-base font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Demo accounts */}
        <section className="border-t border-line py-16">
          <h2 className="text-sm font-medium text-ink-mute">Explore with a demo account</h2>
          <p className="mt-2 max-w-xl text-sm text-ink-soft">
            Each role sees the same Northstar Cloud data with different permissions.
          </p>
          <ul className="mt-6 divide-y divide-line border-y border-line">
            {demoUsers.map((u) => (
              <li key={u.role} className="flex flex-wrap items-center gap-x-6 gap-y-1 py-4">
                <div className="w-52">
                  <p className="text-sm font-medium">{u.name}</p>
                  <p className="text-xs text-ink-mute">{u.role}</p>
                </div>
                <p className="flex-1 min-w-[16rem] text-sm text-ink-soft">{u.about}</p>
                <button
                  onClick={() => enterAs(u.role)}
                  disabled={pending !== null}
                  className="text-sm font-medium text-accent-ink hover:underline underline-offset-2 disabled:opacity-60"
                >
                  {pending === u.role ? "Opening…" : "Enter"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6 text-xs text-ink-mute">
          <span>BrandProof</span>
          <Link href="/login" className="hover:text-ink">
            Sign in
          </Link>
        </div>
      </footer>
    </div>
  );
}
