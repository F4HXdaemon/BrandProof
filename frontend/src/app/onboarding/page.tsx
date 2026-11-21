"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Building2,
  FileText,
  FileCheck2,
  Search,
  Sparkles,
  Layers,
  Scale,
  CheckCheck,
  Check,
  LayoutDashboard,
  PlusCircle,
  BookOpen,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Organization } from "@/lib/types";
import { Button } from "@/components/ui/button";

const STEPS = [
  { id: 1, title: "Welcome", subtitle: "Getting Started" },
  { id: 2, title: "What We Do", subtitle: "Brand Governance" },
  { id: 3, title: "Your Workspace", subtitle: "Organization & Isolation" },
  { id: 4, title: "Submitting Content", subtitle: "Intent Cards & Ingestion" },
  { id: 5, title: "Evidence & Rules", subtitle: "The Citation Gate" },
  { id: 6, title: "Main Dashboard", subtitle: "Ready to Verify" },
];

export default function OnboardingPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState(1);
  const [org, setOrg] = useState<Organization | null>(null);
  const [loadingOrg, setLoadingOrg] = useState(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/onboarding");
      return;
    }

    async function fetchOrg() {
      try {
        const currentOrg = await api.organizations.getCurrent();
        setOrg(currentOrg);
      } catch (err) {
        console.warn("Could not load organization in onboarding:", err);
      } finally {
        setLoadingOrg(false);
      }
    }

    if (isAuthenticated) {
      fetchOrg();
    }
  }, [isLoading, isAuthenticated, router]);

  const handleNext = () => {
    if (currentStep < 6) {
      setCurrentStep((prev) => prev + 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      router.push("/dashboard");
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  if (isLoading || loadingOrg) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-ink-mute">Preparing your BrandProof workspace…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col">
      {/* Top Banner Navigation */}
      <header className="border-b border-line bg-paper sticky top-0 z-20">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link href="/dashboard" className="font-serif text-xl font-medium tracking-tight">
            BrandProof
          </Link>
          <div className="flex items-center gap-4 text-xs text-ink-soft">
            <span>Step {currentStep} of 6</span>
            <button
              onClick={() => router.push("/dashboard")}
              className="text-ink-mute hover:text-ink transition-colors font-medium"
            >
              Skip to Dashboard &rarr;
            </button>
          </div>
        </div>
      </header>

      {/* Stepper Progress Bar */}
      <div className="bg-surface border-b border-line">
        <div className="mx-auto max-w-5xl px-6 py-3">
          <div className="grid grid-cols-6 gap-2">
            {STEPS.map((step) => {
              const isPassed = step.id < currentStep;
              const isCurrent = step.id === currentStep;
              return (
                <button
                  key={step.id}
                  onClick={() => setCurrentStep(step.id)}
                  className={`flex flex-col text-left transition-opacity ${
                    isCurrent ? "opacity-100" : isPassed ? "opacity-80 hover:opacity-100" : "opacity-40"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                        isCurrent
                          ? "bg-accent text-ink"
                          : isPassed
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-line-strong text-ink-mute"
                      }`}
                    >
                      {isPassed ? <Check className="w-3 h-3" /> : step.id}
                    </span>
                    <span className="hidden sm:inline text-xs font-medium truncate">{step.title}</span>
                  </div>
                  <div
                    className={`mt-2 h-1 w-full rounded-full transition-colors ${
                      isCurrent ? "bg-accent" : isPassed ? "bg-emerald-500" : "bg-line"
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Guided Content */}
      <main className="flex-1 mx-auto w-full max-w-3xl px-6 py-10">
        {/* Step 1: Welcome to BrandProof */}
        {currentStep === 1 && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <span className="inline-flex items-center gap-1 rounded bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink">
                <Sparkles className="w-3.5 h-3.5" />
                Welcome Onboard
              </span>
              <h1 className="page-title mt-4 text-3xl sm:text-4xl">
                Welcome to BrandProof, {user?.full_name}!
              </h1>
              <p className="mt-3 text-base text-ink-soft leading-relaxed">
                BrandProof is your full-stack brand governance and advertisement verification platform.
                We ensure that every public claim, statistic, and statement made in your marketing is
                anchored directly to verified evidence.
              </p>
            </div>

            <div className="rounded-xl border border-line bg-surface p-6 space-y-4">
              <h2 className="font-serif text-xl font-medium text-ink">The Core BrandProof Philosophy</h2>
              <div className="p-4 rounded-lg bg-paper border border-line-strong">
                <blockquote className="font-serif text-lg italic text-ink">
                  &ldquo;AI proposes. Evidence decides. People approve.&rdquo;
                </blockquote>
                <p className="mt-2 text-xs text-ink-mute font-sans">
                  The immutable BrandProof Invariant: <strong>NO VALID SOURCE = NO FINDING.</strong>
                </p>
              </div>
              <p className="text-sm text-ink-soft leading-relaxed">
                As marketing and ad copy moves faster with generative AI, brand risk increases exponentially.
                BrandProof sits between draft creation and publication, giving your marketing, legal, and compliance
                teams absolute certainty.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="rounded-lg border border-line bg-surface p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-soft text-accent-ink mb-3">
                  <FileText className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-semibold text-ink">Strict Evidence Matching</h3>
                <p className="mt-1 text-xs text-ink-soft">
                  Claims are checked against your organization&apos;s verified Fact Registry.
                </p>
              </div>

              <div className="rounded-lg border border-line bg-surface p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-soft text-accent-ink mb-3">
                  <Scale className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-semibold text-ink">Deterministic Rules</h3>
                <p className="mt-1 text-xs text-ink-soft">
                  Zero-latency detection of banned superlatives, missing disclaimers, and jurisdiction limits.
                </p>
              </div>

              <div className="rounded-lg border border-line bg-surface p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-soft text-accent-ink mb-3">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-semibold text-ink">Human-in-the-Loop</h3>
                <p className="mt-1 text-xs text-ink-soft">
                  AI assists with granular diffing, but certified human reviewers retain final approval.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: What BrandProof Does */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <span className="inline-flex items-center gap-1 rounded bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink">
                <Scale className="w-3.5 h-3.5" />
                System Architecture
              </span>
              <h1 className="page-title mt-4 text-3xl">Understanding What BrandProof Does</h1>
              <p className="mt-2 text-sm text-ink-soft leading-relaxed">
                BrandProof eliminates subjective guesswork in brand compliance through a disciplined 4-stage pipeline.
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-line bg-surface p-5 flex gap-4 items-start">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-ink font-semibold text-xs mt-0.5">
                  1
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-ink">Claim Extraction & Normalization</h3>
                  <p className="mt-1 text-xs text-ink-soft leading-relaxed">
                    Uploaded advertisements, campaign briefs, whitepapers, or ad copy are split into chunks.
                    The platform extracts distinct numerical, technical, and regulatory claims.
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-line bg-surface p-5 flex gap-4 items-start">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-ink font-semibold text-xs mt-0.5">
                  2
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-ink">Knowledge & Evidence Resolution</h3>
                  <p className="mt-1 text-xs text-ink-soft leading-relaxed">
                    BrandProof automatically scopes the draft by product line, geographical market, and media channel.
                    Only facts and guidelines that govern that specific scope are loaded into evaluation.
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-line bg-surface p-5 flex gap-4 items-start">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-ink font-semibold text-xs mt-0.5">
                  3
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-ink">The Citation Gate</h3>
                  <p className="mt-1 text-xs text-ink-soft leading-relaxed">
                    Every flag or citation requires a verified source reference. If a proposed finding cannot be
                    backed by an approved canonical fact or written guideline, it is automatically discarded.
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-line bg-surface p-5 flex gap-4 items-start">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-ink font-semibold text-xs mt-0.5">
                  4
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-ink">Audit Trail & Governance Log</h3>
                  <p className="mt-1 text-xs text-ink-soft leading-relaxed">
                    Every review, edit, suggestion, and approval is written to an immutable append-only audit trail
                    for full regulatory compliance and internal governance.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Your Organization Workspace */}
        {currentStep === 3 && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <span className="inline-flex items-center gap-1 rounded bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink">
                <Building2 className="w-3.5 h-3.5" />
                Tenant Isolation
              </span>
              <h1 className="page-title mt-4 text-3xl">Your Organisation Workspace</h1>
              <p className="mt-2 text-sm text-ink-soft leading-relaxed">
                BrandProof enforces multi-tenant isolation at every database query and storage operation.
              </p>
            </div>

            {/* Current Org Snapshot */}
            <div className="rounded-xl border border-line bg-surface p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-ink-mute font-medium">Active Workspace</p>
                  <h2 className="text-xl font-semibold text-ink mt-0.5">{org?.name || "Your Organization"}</h2>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
                  Isolated Tenant
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs pt-1">
                <div>
                  <span className="text-ink-mute">Workspace Slug:</span>
                  <p className="font-mono font-medium text-ink mt-0.5">{org?.slug || "org-workspace"}</p>
                </div>
                <div>
                  <span className="text-ink-mute">Your Role:</span>
                  <p className="font-semibold text-accent-ink mt-0.5">{user?.role || "Member"}</p>
                </div>
                <div>
                  <span className="text-ink-mute">Organization Domain:</span>
                  <p className="font-medium text-ink mt-0.5">{org?.domain || "Standard Domain"}</p>
                </div>
                <div>
                  <span className="text-ink-mute">Account Status:</span>
                  <p className="font-medium text-emerald-600 mt-0.5">Active & Verified</p>
                </div>
              </div>
            </div>

            {/* Collaboration & Security explanation */}
            <div className="rounded-lg border border-line-strong bg-paper p-5 space-y-3">
              <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-accent-ink" />
                Strict Organization Isolation Guarantee
              </h3>
              <p className="text-xs text-ink-soft leading-relaxed">
                Your brand facts, compliance rules, ad copy drafts, and audit events are cryptographically isolated.
                Users from other organizations cannot query or discover your data.
              </p>
              <div className="mt-3 rounded border border-accent/30 bg-accent-soft p-3 text-xs text-ink">
                <strong>Inviting Team Members:</strong> As an administrator, you can invite creators and reviewers
                using cryptographically signed invite tokens from Organization Settings. Team members join with the
                Creator role and cannot assign themselves privileged administrative access.
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Submitting Content */}
        {currentStep === 4 && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <span className="inline-flex items-center gap-1 rounded bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink">
                <FileCheck2 className="w-3.5 h-3.5" />
                Content Ingestion
              </span>
              <h1 className="page-title mt-4 text-3xl">How to Submit Marketing Content</h1>
              <p className="mt-2 text-sm text-ink-soft leading-relaxed">
                Submissions in BrandProof use an <strong>Intent Card</strong> to provide the essential context
                needed for accurate verification.
              </p>
            </div>

            <div className="rounded-xl border border-line bg-surface p-6 space-y-4">
              <h2 className="text-base font-semibold text-ink">The Intent Card Fields</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="rounded border border-line p-3 bg-paper">
                  <strong className="text-ink font-semibold">1. Campaign Title:</strong>
                  <p className="mt-1 text-ink-soft">Identifies the ad draft (e.g. &ldquo;Q2 Enterprise Cloud Launch&rdquo;).</p>
                </div>
                <div className="rounded border border-line p-3 bg-paper">
                  <strong className="text-ink font-semibold">2. Product Scope:</strong>
                  <p className="mt-1 text-ink-soft">Directs verification to facts governing that specific product.</p>
                </div>
                <div className="rounded border border-line p-3 bg-paper">
                  <strong className="text-ink font-semibold">3. Region Scope:</strong>
                  <p className="mt-1 text-ink-soft">Applies country-specific disclaimers (e.g., EU GDPR vs US FTC rules).</p>
                </div>
                <div className="rounded border border-line p-3 bg-paper">
                  <strong className="text-ink font-semibold">4. Channel Scope:</strong>
                  <p className="mt-1 text-ink-soft">Enforces channel limits (e.g. Character limits on Social vs Billboard).</p>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-surface p-5 space-y-3">
              <h3 className="text-sm font-semibold text-ink">Supported Content Formats</h3>
              <p className="text-xs text-ink-soft leading-relaxed">
                BrandProof supports multiple upload methods:
              </p>
              <ul className="text-xs text-ink-soft space-y-1.5 list-disc list-inside">
                <li><strong>Markdown (.md) & Plain Text (.txt)</strong>: Native headline and paragraph chunking.</li>
                <li><strong>Microsoft Word (.docx)</strong>: Ingests structured paragraphs, tables, and bullet points.</li>
                <li><strong>PDF Documents (.pdf)</strong>: Extracts text while tracking page numbers.</li>
                <li><strong>Direct Paste</strong>: Quick validation of ad headlines, social posts, or email copy.</li>
              </ul>
            </div>
          </div>
        )}

        {/* Step 5: Evidence & Rules */}
        {currentStep === 5 && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <span className="inline-flex items-center gap-1 rounded bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink">
                <Search className="w-3.5 h-3.5" />
                The Citation Gate
              </span>
              <h1 className="page-title mt-4 text-3xl">Understanding Evidence & Evaluations</h1>
              <p className="mt-2 text-sm text-ink-soft leading-relaxed">
                How BrandProof analyzes drafts without hallucination or false alarms.
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-line bg-surface p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold">
                    ✓
                  </span>
                  <h3 className="text-sm font-semibold text-ink">1. Fact Registry Matching</h3>
                </div>
                <p className="text-xs text-ink-soft leading-relaxed pl-8">
                  BrandProof checks metrics against registered canonical facts. If copy claims &ldquo;99.99% uptime&rdquo;,
                  the engine verifies that a current, non-expired SLA fact exists in the registry with an authorized source reference.
                </p>
              </div>

              <div className="rounded-xl border border-line bg-surface p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-800 text-xs font-bold">
                    !
                  </span>
                  <h3 className="text-sm font-semibold text-ink">2. Deterministic Rule Engine</h3>
                </div>
                <p className="text-xs text-ink-soft leading-relaxed pl-8">
                  Configurable rules automatically catch high-risk patterns such as forbidden superlatives (&ldquo;the best&rdquo;, &ldquo;unmatched&rdquo;),
                  unapproved competitor comparisons, missing regulatory disclaimers, or expired performance statistics.
                </p>
              </div>

              <div className="rounded-xl border border-line bg-surface p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-ink text-xs font-bold">
                    ★
                  </span>
                  <h3 className="text-sm font-semibold text-ink">3. Risk Scoring & Recommendations</h3>
                </div>
                <p className="text-xs text-ink-soft leading-relaxed pl-8">
                  The system generates a transparent risk score (Low, Medium, High, or Blocker) with inline suggested
                  remedies so creators can fix issues with a single click.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 6: Main Dashboard Ready */}
        {currentStep === 6 && (
          <div className="space-y-6 animate-fadeIn">
            <div className="text-center py-4">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 mb-4">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h1 className="page-title text-3xl sm:text-4xl">You are ready to verify!</h1>
              <p className="mt-2 text-sm text-ink-soft max-w-md mx-auto leading-relaxed">
                Your workspace <strong className="text-ink">{org?.name}</strong> is completely set up.
                Explore the governance dashboard or submit your first review draft now.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="group rounded-xl border border-line bg-surface p-5 text-left transition-all hover:border-accent hover:shadow-soft"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-soft text-accent-ink">
                    <LayoutDashboard className="w-5 h-5" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-ink-mute group-hover:text-accent-ink transition-transform group-hover:translate-x-1" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-ink">Go to Main Dashboard</h3>
                <p className="mt-1 text-xs text-ink-soft">
                  View risk metrics, active facts, recent audit logs, and pending reviews.
                </p>
              </button>

              <button
                type="button"
                onClick={() => router.push("/reviews/new")}
                className="group rounded-xl border border-line bg-surface p-5 text-left transition-all hover:border-accent hover:shadow-soft"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800">
                    <PlusCircle className="w-5 h-5" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-ink-mute group-hover:text-emerald-800 transition-transform group-hover:translate-x-1" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-ink">Submit First Review</h3>
                <p className="mt-1 text-xs text-ink-soft">
                  Upload an advertisement draft or paste marketing copy for instant evaluation.
                </p>
              </button>
            </div>

            <div className="rounded-lg border border-line bg-paper p-4 flex items-center justify-between text-xs text-ink-soft">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-ink-mute" />
                <span>Need to manage facts, rules, or guidelines?</span>
              </div>
              <Link href="/knowledge/facts" className="font-semibold text-accent-ink hover:underline">
                Explore Fact Registry &rarr;
              </Link>
            </div>
          </div>
        )}

        {/* Footer Navigation Buttons */}
        <div className="mt-10 border-t border-line pt-6 flex items-center justify-between">
          <Button
            type="button"
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 1}
            className="gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Previous
          </Button>

          <Button type="button" onClick={handleNext} className="gap-2">
            {currentStep === 6 ? (
              <>
                Enter BrandProof Dashboard
                <LayoutDashboard className="w-4 h-4" />
              </>
            ) : (
              <>
                Next Step
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </div>
      </main>
    </div>
  );
}
