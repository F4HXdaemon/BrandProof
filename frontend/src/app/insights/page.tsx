"use client";

import React, { useEffect, useState } from "react";
import { PieChart } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { InsightsData } from "@/lib/types";

export default function InsightsPage() {
  const [data, setData] = useState<InsightsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await api.insights.get();
        setData(res);
      } catch (err) {
        console.error("Failed to load insights:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="page-title text-3xl text-ink">Insights</h1>
          <p className="text-xs text-ink-soft mt-1">
            Where findings come from and which rules fire most often.
          </p>
        </div>

        {loading ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Skeleton className="h-64 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          </div>
        ) : data ? (
          <>
            {/* Key figures */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-px overflow-hidden rounded-lg border border-line bg-line">
              <div className="bg-surface px-4 py-4">
                <p className="text-xs text-ink-soft">Reviews checked</p>
                <p className="mt-1 font-serif text-3xl font-medium tabular-nums text-ink">{data.metrics.total_reviews}</p>
                <p className="mt-0.5 text-xs text-ink-mute">documents</p>
              </div>
              <div className="bg-surface px-4 py-4">
                <p className="text-xs text-ink-soft">Open blockers</p>
                <p className={`mt-1 font-serif text-3xl font-medium tabular-nums ${data.metrics.open_blockers > 0 ? "text-rose-400" : "text-ink"}`}>
                  {data.metrics.open_blockers}
                </p>
                <p className="mt-0.5 text-xs text-ink-mute">
                  {data.metrics.open_blockers > 0 ? "publishing locked until resolved" : "nothing blocking publication"}
                </p>
              </div>
              <div className="bg-surface px-4 py-4">
                <p className="text-xs text-ink-soft">Resolution rate</p>
                <p className="mt-1 font-serif text-3xl font-medium tabular-nums text-ink">{data.metrics.resolution_rate_percent}%</p>
                <p className="mt-0.5 text-xs text-ink-mute">
                  {data.metrics.resolved_findings} of {data.metrics.total_findings} findings resolved
                </p>
              </div>
              <div className="bg-surface px-4 py-4">
                <p className="text-xs text-ink-soft">Average risk score</p>
                <p className="mt-1 font-serif text-3xl font-medium tabular-nums text-ink">{data.metrics.average_risk_score}</p>
                <p className="mt-0.5 text-xs text-ink-mute">Blocker 15 · High 7 · Warning 3 · Info 1</p>
              </div>
            </div>

            {/* Severity & Status Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Severity Breakdown */}
              <Card className="p-5 bg-surface border-line">
                <div className="flex items-center justify-between pb-3 border-b border-line">
                  <div>
                    <h3 className="text-sm font-semibold text-ink">Findings by Severity</h3>
                    <p className="text-xs text-ink-soft">Active distribution across all reviews</p>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {[
                    { label: "Blocker", count: data.severity_breakdown.Blocker || 0, color: "bg-rose-500", text: "text-rose-400" },
                    { label: "High", count: data.severity_breakdown.High || 0, color: "bg-orange-500", text: "text-orange-400" },
                    { label: "Warning", count: data.severity_breakdown.Warning || 0, color: "bg-amber-500", text: "text-amber-400" },
                    { label: "Info", count: data.severity_breakdown.Info || 0, color: "bg-sky-500", text: "text-sky-400" },
                  ].map((item) => {
                    const total = data.metrics.total_findings || 1;
                    const pct = Math.round((item.count / total) * 100);
                    return (
                      <div key={item.label}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className={`font-semibold ${item.text}`}>{item.label}</span>
                          <span className="text-ink-soft">{item.count} ({pct}%)</span>
                        </div>
                        <div className="w-full bg-sunken rounded-full h-2 overflow-hidden">
                          <div
                            className={`${item.color} h-2 rounded-full transition-all duration-500`}
                            style={{ width: `${Math.max(pct, item.count > 0 ? 5 : 0)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Claim Verification Ledger Breakdown */}
              <Card className="p-5 bg-surface border-line">
                <div className="flex items-center justify-between pb-3 border-b border-line">
                  <div>
                    <h3 className="text-sm font-semibold text-ink">Claim Verification Ledger Status</h3>
                    <p className="text-xs text-ink-soft">Telemetry from factual claim extraction engine</p>
                  </div>
                  <PieChart className="w-4 h-4 text-emerald-400" />
                </div>

                <div className="mt-4 space-y-2.5">
                  {Object.entries(data.claims_breakdown).length === 0 ? (
                    <p className="text-xs text-ink-mute py-4">No extracted claims recorded yet.</p>
                  ) : (
                    Object.entries(data.claims_breakdown).map(([status, count]) => (
                      <div key={status} className="flex items-center justify-between p-2.5 rounded-lg bg-paper border border-line">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${
                            status === "SUPPORTED" ? "bg-emerald-400" :
                            status === "CONFLICTS" ? "bg-rose-400" :
                            status === "EXPIRED" ? "bg-amber-400" :
                            status === "OUT_OF_SCOPE" ? "bg-purple-400" : "bg-sunken"
                          }`} />
                          <span className="text-xs font-medium text-ink">{status}</span>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          {count} claims
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </Card>
            </div>

            {/* Top Hotspots: Rules & Terminology */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Violated Rules */}
              <Card className="p-5 bg-surface border-line">
                <div className="flex items-center justify-between pb-3 border-b border-line">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-ink">Top Violated Governance Rules</h3>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {data.top_violated_rules.length === 0 ? (
                    <p className="text-xs text-ink-mute py-4">No rule violations detected.</p>
                  ) : (
                    data.top_violated_rules.map((r, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-paper border border-line text-xs">
                        <span className="font-medium text-ink truncate max-w-xs">{r.name}</span>
                        <Badge variant="outline" className="bg-rose-500/20 text-rose-300 border-rose-500/30">
                          {r.count} violations
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </Card>

              {/* Top Violated Terminology */}
              <Card className="p-5 bg-surface border-line">
                <div className="flex items-center justify-between pb-3 border-b border-line">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-ink">Top Prohibited Brand Variants</h3>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {data.top_violated_terms.length === 0 ? (
                    <p className="text-xs text-ink-mute py-4">No disallowed terminology detected.</p>
                  ) : (
                    data.top_violated_terms.map((t, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-paper border border-line text-xs">
                        <span className="font-mono text-amber-300 font-semibold">{t.term}</span>
                        <Badge variant="outline" className="border-amber-500/30 text-amber-300 bg-amber-500/10">
                          {t.count} occurrences
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </Card>
            </div>
          </>
        ) : (
          <p className="text-xs text-ink-mute">Failed to load analytics telemetry.</p>
        )}
      </div>
    </AppShell>
  );
}
