"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { DashboardData } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

import { useAuth } from "@/context/auth-context";

/** "FACT_UPDATED" -> "Fact updated" */
function humanizeAction(action: string): string {
  const s = action.replace(/[_.]+/g, " ").trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [orgName, setOrgName] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async () => {
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
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

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
          <Button variant="ghost" size="sm" onClick={fetchDashboard} isLoading={loading}>
            {!loading && <RefreshCw className="w-3.5 h-3.5" />}
            Refresh
          </Button>
        </div>

        {/* Onboarding Banner for New Workspaces */}
        {!loading && !error && (m?.open_reviews ?? 0) === 0 && (data?.recent_reviews?.length ?? 0) === 0 && (
          <div className="rounded-lg border border-accent/40 bg-accent-soft p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-ink">Welcome to your BrandProof workspace</h2>
                <p className="mt-1 text-xs text-ink-soft max-w-xl">
                  Register your brand&apos;s verified claims and facts, establish guidelines and terminology rules, or initiate your first draft review.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <Link
                  href="/reviews/new"
                  className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-ink hover:bg-accent-hover transition-colors"
                >
                  New Review
                </Link>
                <Link
                  href="/knowledge/facts"
                  className="rounded-md border border-line-strong bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-sunken transition-colors"
                >
                  Add Fact
                </Link>
                <Link
                  href="/knowledge/guidelines"
                  className="rounded-md border border-line-strong bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-sunken transition-colors"
                >
                  Guidelines
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
      </div>
    </AppShell>
  );
}
