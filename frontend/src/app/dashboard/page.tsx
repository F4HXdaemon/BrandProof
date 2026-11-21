"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  RefreshCw,
  Sparkles,
  CheckCircle2,
  Circle,
  ArrowRight,
  FileText,
  Upload,
  FileCheck,
  Scale,
  Compass,
  Play,
  Download,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductTourModal } from "@/components/onboarding/product-tour-modal";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { DashboardData } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

/** "FACT_UPDATED" -> "Fact updated" */
function humanizeAction(action: string): string {
  const s = action.replace(/[_.]+/g, " ").trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function DashboardPage() {
  const { user, completeOnboarding } = useAuth();
  const { success, error: toastError, info } = useToast();
  const [data, setData] = useState<DashboardData | null>(null);
  const [orgName, setOrgName] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showTour, setShowTour] = useState(false);
  const [creatingDemo, setCreatingDemo] = useState(false);
  const [reportDownloaded, setReportDownloaded] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setReportDownloaded(localStorage.getItem("brandproof_report_downloaded") === "true");
    }
  }, []);

  // Launch product tour automatically on first login if not yet completed
  useEffect(() => {
    if (user && user.onboarding_completed === false) {
      setShowTour(true);
    }
  }, [user]);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, orgRes] = await Promise.allSettled([
        api.dashboard.getMetrics(),
        api.organizations.getCurrent(),
      ]);

      if (res.status === "fulfilled") {
        setData(res.value);
      } else {
        throw res.reason;
      }

      if (orgRes.status === "fulfilled" && orgRes.value?.name) {
        setOrgName(orgRes.value.name);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const handleGenerateSampleEvaluation = async () => {
    setCreatingDemo(true);
    try {
      const res = await api.evaluation.create({
        title: "Northstar Cloud Enterprise Q3 Announcement",
        content:
          "Northstar Cloud guarantees 99.99% uptime across all availability zones. " +
          "Our ISO 27001 certified platform cuts onboarding time by 60% compared to legacy architectures. " +
          "Instant automated compliance guardrails active from day one.",
        product: "Northstar Pro",
        region: "Global",
        channel: "Advertisement",
        content_type: "Ad Copy",
        intended_audience: "Enterprise IT Decision Makers",
        purpose: "Demonstrate verified uptime, SLA performance, and cloud governance",
        supporting_evidence: "Doc Ref #CERT-2026-99",
      });

      success(
        "Sample Evaluation Created",
        `Created "${res.title}" with live CitationGate findings and risk telemetry.`
      );
      await fetchDashboard();
    } catch (err: any) {
      toastError("Sample Creation Failed", err.message || "Failed to create sample evaluation.");
    } finally {
      setCreatingDemo(false);
    }
  };

  const m = data?.metrics;
  const risk = data?.risk_overview;
  const displayName = orgName || "your organization";

  // Only colour a number when it is something to act on.
  const stats = [
    { label: "Open reviews", value: m?.open_reviews ?? 0, note: "in progress", tone: "" },
    { label: "Blocked", value: m?.blocked_content ?? 0, note: "need action", tone: (m?.blocked_content ?? 0) > 0 ? "text-rose-400" : "" },
    { label: "Approved this week", value: m?.approved_this_week ?? 0, note: "ready to publish", tone: "" },
    { label: "Active facts", value: m?.active_facts ?? 0, note: "in the registry", tone: "" },
    { label: "Expiring facts", value: m?.expiring_facts ?? 0, note: "within 30 days", tone: (m?.expiring_facts ?? 0) > 0 ? "text-amber-400" : "" },
    { label: "Findings this month", value: m?.findings_this_month ?? 0, note: "flagged", tone: "" },
  ];

  const severities = [
    { label: "Critical", value: risk?.findings_by_severity?.critical ?? 0, tone: "text-rose-400" },
    { label: "High", value: risk?.findings_by_severity?.high ?? 0, tone: "text-amber-400" },
    { label: "Medium", value: risk?.findings_by_severity?.medium ?? 0, tone: "" },
    { label: "Low", value: risk?.findings_by_severity?.low ?? 0, tone: "" },
    { label: "Advisory", value: risk?.findings_by_severity?.advisory ?? 0, tone: "" },
  ];

  const step1Done = (data?.recent_reviews?.length ?? 0) > 0;
  const step2Done = (m?.active_facts ?? 0) > 0 || (data?.recent_activity?.length ?? 0) > 0;
  const step3Done = step1Done;
  const step4Done = reportDownloaded;
  const completedSteps = [step1Done, step2Done, step3Done, step4Done].filter(Boolean).length;
  const progressPercent = Math.round((completedSteps / 4) * 100);

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Overview</h1>
            <p className="text-sm text-ink-soft mt-1">
              Where drafts and approved facts stand for {displayName}.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTour(true)}
              className="text-xs bg-surface border-line-strong hover:bg-sunken text-ink"
            >
              <Compass className="w-3.5 h-3.5 mr-1 text-accent" />
              <span>Product Tour</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={fetchDashboard} isLoading={loading}>
              {!loading && <RefreshCw className="w-3.5 h-3.5" />}
              Refresh
            </Button>
          </div>
        </div>

        {/* Guided First-Time Experience Checklist Card */}
        {!loading && (
          <div className="rounded-xl border border-line bg-surface p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded-md bg-accent-soft text-accent-ink">
                    <Sparkles className="w-4 h-4" />
                  </span>
                  <h2 className="text-sm font-semibold text-ink">Getting Started Checklist</h2>
                  <Badge variant="status" value={completedSteps === 4 ? "Approved" : "In Progress"} />
                </div>
                <p className="mt-1 text-xs text-ink-soft max-w-xl">
                  Follow this 4-step sequence to run an evaluation, verify claims against evidence, and download certified reports.
                </p>
              </div>

              <div className="flex items-center gap-2.5 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleGenerateSampleEvaluation}
                  isLoading={creatingDemo}
                  disabled={creatingDemo}
                  className="bg-accent/10 border-accent/30 text-accent hover:bg-accent/20 text-xs font-semibold"
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  <span>{creatingDemo ? "Generating..." : "Generate Sample Evaluation"}</span>
                </Button>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink-soft font-medium">Checklist Progress: {completedSteps} of 4 steps completed</span>
                <span className="font-mono font-semibold text-accent-ink">{progressPercent}%</span>
              </div>
              <div className="w-full bg-paper rounded-full h-2 overflow-hidden border border-line">
                <div
                  className="bg-accent h-2 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>

            {/* Checklist Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
              {/* Step 1 */}
              <div className={`p-3 rounded-lg border transition-all ${
                step1Done ? "bg-emerald-950/20 border-emerald-500/30" : "bg-paper border-line"
              }`}>
                <div className="flex items-start justify-between">
                  <span className="text-[11px] font-semibold text-ink-mute uppercase tracking-wider">Step 1</span>
                  {step1Done ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-ink-mute shrink-0" />
                  )}
                </div>
                <p className="text-xs font-medium text-ink mt-1.5">Create First Evaluation</p>
                <p className="text-[11px] text-ink-mute mt-0.5 line-clamp-2">
                  Submit ad copy or campaign text for automated claim parsing.
                </p>
                <Link
                  href="/reviews/new"
                  className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent-ink hover:underline"
                >
                  <span>{step1Done ? "Run Another" : "Start Evaluation"}</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {/* Step 2 */}
              <div className={`p-3 rounded-lg border transition-all ${
                step2Done ? "bg-emerald-950/20 border-emerald-500/30" : "bg-paper border-line"
              }`}>
                <div className="flex items-start justify-between">
                  <span className="text-[11px] font-semibold text-ink-mute uppercase tracking-wider">Step 2</span>
                  {step2Done ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-ink-mute shrink-0" />
                  )}
                </div>
                <p className="text-xs font-medium text-ink mt-1.5">Upload Supporting Evidence</p>
                <p className="text-[11px] text-ink-mute mt-0.5 line-clamp-2">
                  Register facts or upload certified evidence docs/images.
                </p>
                <Link
                  href="/evidence"
                  className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent-ink hover:underline"
                >
                  <span>{step2Done ? "Manage Evidence" : "Upload Evidence"}</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {/* Step 3 */}
              <div className={`p-3 rounded-lg border transition-all ${
                step3Done ? "bg-emerald-950/20 border-emerald-500/30" : "bg-paper border-line"
              }`}>
                <div className="flex items-start justify-between">
                  <span className="text-[11px] font-semibold text-ink-mute uppercase tracking-wider">Step 3</span>
                  {step3Done ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-ink-mute shrink-0" />
                  )}
                </div>
                <p className="text-xs font-medium text-ink mt-1.5">Inspect Findings & Results</p>
                <p className="text-[11px] text-ink-mute mt-0.5 line-clamp-2">
                  Review CitationGate matches, risk scores, and claim ledgers.
                </p>
                <Link
                  href="/reviews"
                  className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent-ink hover:underline"
                >
                  <span>View Findings</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {/* Step 4 */}
              <div className={`p-3 rounded-lg border transition-all ${
                step4Done ? "bg-emerald-950/20 border-emerald-500/30" : "bg-paper border-line"
              }`}>
                <div className="flex items-start justify-between">
                  <span className="text-[11px] font-semibold text-ink-mute uppercase tracking-wider">Step 4</span>
                  {step4Done ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-ink-mute shrink-0" />
                  )}
                </div>
                <p className="text-xs font-medium text-ink mt-1.5">Download Official PDF Report</p>
                <p className="text-[11px] text-ink-mute mt-0.5 line-clamp-2">
                  Export boardroom-ready compliance audit reports.
                </p>
                <Link
                  href="/evaluation"
                  className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent-ink hover:underline"
                >
                  <span>{step4Done ? "Export More" : "Export Report"}</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-between rounded-lg border border-rose-500/30 bg-rose-950 px-4 py-3 text-sm text-rose-300">
            <span>{error}</span>
            <button onClick={fetchDashboard} className="font-medium underline underline-offset-2">
              Retry
            </button>
          </div>
        )}

        {/* Key figures: one ruled strip, no icons */}
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-px overflow-hidden rounded-lg border border-line bg-line">
          {stats.map((s) => (
            <div key={s.label} className="bg-surface px-4 py-4">
              <p className="text-xs text-ink-soft">{s.label}</p>
              {loading ? (
                <Skeleton className="mt-2 h-8 w-12" />
              ) : (
                <p className={cn("mt-1 font-serif text-3xl font-medium tabular-nums text-ink", s.tone)}>
                  {s.value}
                </p>
              )}
              <p className="mt-0.5 text-xs text-ink-mute">{s.note}</p>
            </div>
          ))}
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Recent reviews */}
          <Card className="lg:col-span-2 p-0">
            <CardHeader className="px-5 pt-5">
              <div>
                <CardTitle>Recent reviews</CardTitle>
                <CardDescription>Latest drafts checked against approved sources</CardDescription>
              </div>
              <Link href="/reviews" className="text-sm text-accent-ink hover:underline underline-offset-2">
                View all
              </Link>
            </CardHeader>

            {loading ? (
              <div className="space-y-3 px-5 pb-5">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : data?.recent_reviews && data.recent_reviews.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-xs text-ink-mute border-b border-line">
                      <th className="px-5 pb-2 font-medium">Draft</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium text-right">Findings</th>
                      <th className="px-5 pb-2 font-medium text-right">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.recent_reviews.map((r) => (
                      <tr key={r.id} className="hover:bg-sunken/60 transition-colors">
                        <td className="px-5 py-3">
                          <Link href={`/reviews/${r.id}`} className="font-medium text-ink hover:text-accent-ink">
                            {r.document_title || "Untitled draft"}
                          </Link>
                          <p className="text-xs text-ink-mute">{r.reviewer_name || "Unassigned"}</p>
                        </td>
                        <td className="py-3">
                          <Badge variant="status" value={r.status} />
                        </td>
                        <td className={cn("py-3 text-right tabular-nums", r.findings_count > 0 ? "text-ink" : "text-ink-mute")}>
                          {r.findings_count}
                        </td>
                        <td className="px-5 py-3 text-right text-xs text-ink-soft whitespace-nowrap">
                          {formatRelativeTime(r.updated_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-5 pb-8 pt-2 text-sm text-ink-soft">
                No reviews yet.{" "}
                <Link href="/reviews/new" className="text-accent-ink underline underline-offset-2">
                  Start one
                </Link>
                .
              </p>
            )}
          </Card>

          {/* Risk summary */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Brand safety</CardTitle>
                <CardDescription>Across all active drafts</CardDescription>
              </div>
            </CardHeader>

            {loading ? (
              <div className="space-y-4">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-28 w-full" />
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="font-serif text-5xl font-medium tabular-nums text-ink leading-none">
                      {risk?.overall_score ?? 100}
                      <span className="ml-1 font-sans text-sm text-ink-mute">/ 100</span>
                    </p>
                    <p className="mt-2 text-sm text-ink-soft">{risk?.status}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-ink-mute">Unverified claims</p>
                    <p className="text-lg font-medium tabular-nums text-ink">
                      {risk?.unverified_claims_rate ?? 0}%
                    </p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-ink-mute mb-1">Open issues by severity</p>
                  <dl className="divide-y divide-line border-y border-line">
                    {severities.map((s) => (
                      <div key={s.label} className="flex items-center justify-between py-2 text-sm">
                        <dt className="text-ink-soft">{s.label}</dt>
                        <dd className={cn("tabular-nums", s.value > 0 && s.tone ? s.tone : "text-ink")}>
                          {s.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Activity */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>Latest governance events</CardDescription>
            </div>
            <Link href="/audit" className="text-sm text-accent-ink hover:underline underline-offset-2">
              Full audit log
            </Link>
          </CardHeader>

          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : data?.recent_activity && data.recent_activity.length > 0 ? (
            <ul className="divide-y divide-line">
              {data.recent_activity.map((event) => (
                <li key={event.id} className="flex items-baseline gap-4 py-2.5 text-sm">
                  <span className="w-24 shrink-0 text-xs text-ink-mute">
                    {formatRelativeTime(event.timestamp)}
                  </span>
                  <span className="text-ink">
                    <span className="font-medium">{event.actor_name || "System"}</span>
                    <span className="text-ink-soft">
                      {" "}
                      · {humanizeAction(event.action)} · {event.entity_type}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-4 text-sm text-ink-soft">No events recorded yet.</p>
          )}
        </Card>

        <ProductTourModal
          isOpen={showTour}
          onClose={() => {
            setShowTour(false);
            completeOnboarding();
          }}
          onComplete={() => {
            setShowTour(false);
            completeOnboarding();
            success("Product Tour Completed", "You are ready to run brand evaluations and verify claims!");
          }}
        />
      </div>
    </AppShell>
  );
}
