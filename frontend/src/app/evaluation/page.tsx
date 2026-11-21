"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Target,
  Play,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  ShieldCheck,
  Plus,
  Search,
  Filter,
  RefreshCw,
  ArrowRight,
  ShieldAlert,
  Clock,
  Layers,
  Compass,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { EvaluationResult, EvaluationCase, Review } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

export default function EvaluationPage() {
  const { success, error } = useToast();

  // Tab State: "evaluations" | "benchmark"
  const [activeTab, setActiveTab] = useState<"evaluations" | "benchmark">("evaluations");

  // Evaluations Tab State
  const [evaluations, setEvaluations] = useState<Review[]>([]);
  const [loadingEvals, setLoadingEvals] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [productFilter, setProductFilter] = useState("All");

  // Benchmark Tab State
  const [benchmarkData, setBenchmarkData] = useState<EvaluationResult | null>(null);
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [selectedCase, setSelectedCase] = useState<EvaluationCase | null>(null);
  const [downloadingReportId, setDownloadingReportId] = useState<string | null>(null);
  const hasLoadedBenchmark = useRef(false);

  const handleDownloadReport = async (evalId: string, title?: string) => {
    setDownloadingReportId(evalId);
    try {
      const clean = (title || "evaluation").toLowerCase().replace(/[^a-z0-9_-]/g, "_");
      await api.evaluation.downloadReport(evalId, `${clean}_audit_report.pdf`);
      success("Report Downloaded", "Audit report downloaded successfully.");
    } catch (err: any) {
      error("Report Failed", err.message || "Failed to download audit report.");
    } finally {
      setDownloadingReportId(null);
    }
  };

  // Load Real Brand Evaluations
  const loadEvaluations = useCallback(async () => {
    setLoadingEvals(true);
    try {
      const res = await api.evaluation.list({
        status: statusFilter === "All" ? undefined : statusFilter,
        product: productFilter === "All" ? undefined : productFilter,
        q: submittedQuery.trim() || undefined,
      });
      setEvaluations(res);
    } catch (err: any) {
      console.error("Failed to load evaluations:", err);
    } finally {
      setLoadingEvals(false);
    }
  }, [statusFilter, productFilter, submittedQuery]);

  // Load Benchmark Results
  const loadBenchmark = useCallback(async () => {
    setRunningBenchmark(true);
    try {
      const res = await api.evaluation.run();
      setBenchmarkData(res);
      if (res.cases.length > 0) {
        setSelectedCase(res.cases[0]);
      }
    } catch (err: any) {
      console.error("Benchmark run failed:", err);
      error("Benchmark Failed", err.message || "Failed to execute benchmark evaluation.");
    } finally {
      setLoadingBenchmark(false);
      setRunningBenchmark(false);
    }
  }, [error]);

  useEffect(() => {
    loadEvaluations();
  }, [loadEvaluations]);

  useEffect(() => {
    if (activeTab === "benchmark" && !hasLoadedBenchmark.current) {
      hasLoadedBenchmark.current = true;
      setLoadingBenchmark(true);
      loadBenchmark();
    }
  }, [activeTab, loadBenchmark]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery === submittedQuery) {
      loadEvaluations();
    } else {
      setSubmittedQuery(searchQuery);
    }
  };

  const handleExportCsv = async () => {
    try {
      await api.evaluation.downloadCsv();
    } catch (err: any) {
      console.error("Export CSV failed:", err);
      error("Export Failed", err.message || "Failed to download evaluation CSV.");
    }
  };

  // Evaluation Metrics calculations
  const totalEvals = evaluations.length;
  const needsReviewCount = evaluations.filter((e) => e.status === "Needs Review" || e.status === "In Progress").length;
  const approvedCount = evaluations.filter((e) => e.status === "Approved").length;
  const blockedCount = evaluations.filter(
    (e) => e.risk_level === "High" || e.risk_level === "Critical" || e.status === "Rejected"
  ).length;
  const avgRiskScore =
    totalEvals > 0
      ? (evaluations.reduce((acc, curr) => acc + (curr.risk_score || 0), 0) / totalEvals).toFixed(1)
      : "0.0";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Brand Evaluation</h1>
            <p className="text-xs text-ink-soft mt-1">
              Automated brand compliance evaluations, CitationGate verification, and benchmark test suite.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {activeTab === "benchmark" ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportCsv}
                  className="text-xs border-line-strong hover:bg-sunken text-ink"
                >
                  <Download className="w-3.5 h-3.5 mr-1.5" />
                  Export CSV
                </Button>
                <Button
                  size="sm"
                  onClick={loadBenchmark}
                  disabled={runningBenchmark}
                  className="text-xs bg-accent hover:bg-accent-hover text-ink font-medium"
                >
                  <Play className={`w-3.5 h-3.5 mr-1.5 ${runningBenchmark ? "animate-spin" : ""}`} />
                  {runningBenchmark ? "Running Benchmark..." : "Re-Run Benchmark"}
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadEvaluations}
                  disabled={loadingEvals}
                  className="text-xs border-line-strong hover:bg-sunken text-ink"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loadingEvals ? "animate-spin" : ""}`} />
                  Refresh
                </Button>
                <Link href="/evaluation/new">
                  <Button size="sm" className="text-xs bg-accent hover:bg-accent-hover text-ink font-semibold">
                    <Plus className="w-3.5 h-3.5 mr-1.5" />
                    New Brand Evaluation
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2 border-b border-line pb-px">
          <button
            type="button"
            onClick={() => setActiveTab("evaluations")}
            className={`text-xs font-semibold pb-3 px-3 border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "evaluations"
                ? "border-accent text-accent-ink"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Active Brand Evaluations ({evaluations.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("benchmark")}
            className={`text-xs font-semibold pb-3 px-3 border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "benchmark"
                ? "border-accent text-accent-ink"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            <Target className="w-4 h-4" />
            <span>Ground Truth Benchmark Suite</span>
          </button>
        </div>

        {/* TAB 1: ACTIVE BRAND EVALUATIONS */}
        {activeTab === "evaluations" && (
          <div className="space-y-6">
            {/* Top Score Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <Card className="p-3.5 bg-surface border-line">
                <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider block">
                  Total Evaluations
                </span>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-ink">{totalEvals}</span>
                </div>
                <p className="text-[10px] text-ink-mute mt-0.5">Persisted in organization</p>
              </Card>

              <Card className="p-3.5 bg-surface border-line">
                <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider block">
                  Needs Review
                </span>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-amber-400">{needsReviewCount}</span>
                </div>
                <p className="text-[10px] text-ink-mute mt-0.5">Pending human sign-off</p>
              </Card>

              <Card className="p-3.5 bg-surface border-line">
                <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider block">
                  Approved
                </span>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-emerald-400">{approvedCount}</span>
                </div>
                <p className="text-[10px] text-ink-mute mt-0.5">Cleared for publication</p>
              </Card>

              <Card className="p-3.5 bg-surface border-line">
                <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider block">
                  Flagged / High Risk
                </span>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-rose-400">{blockedCount}</span>
                </div>
                <p className="text-[10px] text-ink-mute mt-0.5">Contains blocker findings</p>
              </Card>

              <Card className="p-3.5 bg-surface border-line">
                <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider block">
                  Avg Risk Score
                </span>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-accent-ink">{avgRiskScore}</span>
                  <span className="text-[11px] text-ink-mute">pts</span>
                </div>
                <p className="text-[10px] text-ink-mute mt-0.5">CitationGate weighted</p>
              </Card>
            </div>

            {/* Filter & Search Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg bg-surface border border-line">
              <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by evaluation title, campaign, or summary..."
                    className="w-full bg-paper border border-line-strong rounded-lg pl-9 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>
                <Button type="submit" size="sm" variant="outline" className="text-xs border-line-strong text-ink h-8">
                  Search
                </Button>
              </form>

              <div className="flex items-center gap-2">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                >
                  <option value="All">All Statuses</option>
                  <option value="Needs Review">Needs Review</option>
                  <option value="Approved">Approved</option>
                  <option value="Changes Requested">Changes Requested</option>
                  <option value="Rejected">Rejected</option>
                </select>

                <select
                  value={productFilter}
                  onChange={(e) => setProductFilter(e.target.value)}
                  className="bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                >
                  <option value="All">All Products</option>
                  <option value="Northstar Pro">Northstar Pro</option>
                  <option value="Northstar Sovereign Cloud">Northstar Sovereign Cloud</option>
                  <option value="CloudShield Intelligence">CloudShield Intelligence</option>
                </select>
              </div>
            </div>

            {/* Evaluations List */}
            {loadingEvals ? (
              <div className="space-y-3">
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : evaluations.length > 0 ? (
              <div className="space-y-3">
                {evaluations.map((ev) => {
                  const isBlocked = ev.risk_level === "High" || ev.risk_level === "Critical";
                  const isApproved = ev.status === "Approved";

                  return (
                    <div
                      key={ev.id}
                      className="p-4 rounded-lg bg-surface border border-line hover:border-line-strong transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      <div className="space-y-2 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/reviews/${ev.id}`}
                            className="text-sm font-semibold text-ink hover:text-accent-ink transition-colors"
                          >
                            {ev.title || "Untitled Brand Evaluation"}
                          </Link>

                          {/* Risk Badge */}
                          <span
                            className={`text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full border ${
                              ev.risk_level === "Critical"
                                ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                                : ev.risk_level === "High"
                                ? "bg-orange-500/15 text-orange-400 border-orange-500/30"
                                : ev.risk_level === "Medium"
                                ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                                : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                            }`}
                          >
                            Risk: {ev.risk_score} ({ev.risk_level})
                          </span>

                          {/* Status Badge */}
                          <Badge
                            variant="outline"
                            className={`text-[11px] ${
                              isApproved
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : ev.status === "Changes Requested"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : isBlocked
                                ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                                : "bg-sunken text-ink-soft border-line-strong"
                            }`}
                          >
                            {ev.status}
                          </Badge>
                        </div>

                        {ev.summary && (
                          <p className="text-xs text-ink-soft line-clamp-1">{ev.summary}</p>
                        )}

                        {/* Metadata Tags */}
                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-mute">
                          <span className="flex items-center gap-1 font-mono text-ink-soft">
                            <Compass className="w-3 h-3 text-accent-ink" />
                            {ev.product || "All Products"} • {ev.region || "Global"} • {ev.channel || "All Channels"}
                          </span>
                          {ev.content_type && (
                            <span className="bg-paper px-2 py-0.5 rounded border border-line">
                              {ev.content_type}
                            </span>
                          )}
                          <span>Claims: {ev.claims_count ?? 0}</span>
                          <span>Findings: {ev.findings_count ?? 0}</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatRelativeTime(ev.created_at)}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownloadReport(ev.id, ev.title)}
                          isLoading={downloadingReportId === ev.id}
                          className="text-xs border-line-strong text-ink hover:bg-sunken"
                          title="Download PDF Report"
                        >
                          <Download className="w-3 h-3 mr-1 text-accent-ink" />
                          Report
                        </Button>

                        <Link href={`/reviews/${ev.id}`}>
                          <Button size="sm" variant="outline" className="text-xs border-line-strong text-ink hover:bg-sunken">
                            Open Workspace
                            <ArrowRight className="w-3 h-3 ml-1.5" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<FileText className="w-8 h-8" />}
                title="No Brand Evaluations Found"
                description="Create a new brand evaluation to verify marketing copy against approved brand facts, guidelines, and rules."
                action={
                  <Link href="/evaluation/new">
                    <Button size="sm" className="bg-accent hover:bg-accent-hover text-ink text-xs font-semibold">
                      <Plus className="w-3.5 h-3.5 mr-1" />
                      Create First Brand Evaluation
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        )}

        {/* TAB 2: GROUND TRUTH BENCHMARK */}
        {activeTab === "benchmark" && (
          <div className="space-y-6">
            {loadingBenchmark ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Skeleton className="h-28 w-full" />
                  <Skeleton className="h-28 w-full" />
                  <Skeleton className="h-28 w-full" />
                  <Skeleton className="h-28 w-full" />
                </div>
                <Skeleton className="h-96 w-full" />
              </div>
            ) : benchmarkData ? (
              <>
                {/* Top Score Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="p-4 bg-surface border-line">
                    <span className="text-xs font-semibold text-ink-soft">Precision</span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold text-emerald-400">
                        {(benchmarkData.metrics.precision * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-mute mt-1">TP / (TP + FP) — Low false alarm rate</p>
                  </Card>

                  <Card className="p-4 bg-surface border-line">
                    <span className="text-xs font-semibold text-ink-soft">Recall</span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold text-accent-ink">
                        {(benchmarkData.metrics.recall * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-mute mt-1">TP / (TP + FN) — High violation capture</p>
                  </Card>

                  <Card className="p-4 bg-surface border-line">
                    <span className="text-xs font-semibold text-ink-soft">F1 Score</span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold text-ink">
                        {benchmarkData.metrics.f1_score.toFixed(3)}
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-mute mt-1">Harmonic mean of precision and recall</p>
                  </Card>

                  <Card className="p-4 bg-surface border-line">
                    <span className="text-xs font-semibold text-ink-soft">Detection Accuracy</span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-3xl font-semibold text-emerald-400">
                        {benchmarkData.metrics.accuracy_percent}%
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-mute mt-1">
                      {benchmarkData.metrics.true_positives} TP · {benchmarkData.metrics.false_positives} FP ·{" "}
                      {benchmarkData.metrics.false_negatives} FN
                    </p>
                  </Card>
                </div>

                {/* Split View: Test Cases List & Case Detail */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Cases List */}
                  <div className="lg:col-span-5 space-y-3">
                    <div className="flex items-center justify-between text-xs text-ink-soft px-1 font-semibold">
                      <span>Benchmark Cases ({benchmarkData.cases.length})</span>
                      <span>Status</span>
                    </div>

                    <div className="space-y-2">
                      {benchmarkData.cases.map((c) => {
                        const isSelected = selectedCase?.case_id === c.case_id;
                        const isPass = c.false_negatives === 0 && c.false_positives === 0;

                        return (
                          <div
                            key={c.case_id}
                            onClick={() => setSelectedCase(c)}
                            className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                              isSelected
                                ? "bg-accent-soft border-accent"
                                : "bg-surface border-line hover:border-line-strong"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-ink truncate">{c.title}</span>
                              {isPass ? (
                                <Badge
                                  variant="outline"
                                  className="text-[11px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                >
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                  PASS
                                </Badge>
                              ) : (
                                <Badge
                                  variant="outline"
                                  className="text-[11px] bg-amber-500/10 text-amber-400 border-amber-500/20"
                                >
                                  <AlertTriangle className="w-3 h-3 mr-1" />
                                  PARTIAL
                                </Badge>
                              )}
                            </div>

                            <p className="text-xs text-ink-soft line-clamp-1 mt-1 font-mono text-[11px]">
                              {c.text}
                            </p>

                            <div className="flex items-center gap-3 mt-2 text-[11px] text-ink-mute">
                              <span>TP: {c.true_positives}</span>
                              <span>FP: {c.false_positives}</span>
                              <span>FN: {c.false_negatives}</span>
                              <span className="text-ink-soft font-semibold">{c.case_id}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Detail View */}
                  <div className="lg:col-span-7">
                    {selectedCase ? (
                      <Card className="p-5 bg-surface border-line space-y-4">
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-accent-ink">{selectedCase.case_id}</span>
                            <Badge variant="outline" className="text-xs">
                              {selectedCase.detected_count} / {selectedCase.expected_count} Findings Verified
                            </Badge>
                          </div>
                          <h2 className="text-base font-semibold text-ink mt-1">{selectedCase.title}</h2>
                        </div>

                        {/* Test Text Sample */}
                        <div className="p-3.5 rounded-lg bg-paper border border-line">
                          <span className="text-[11px] font-semibold text-ink-mute block mb-1">
                            Input Test Draft
                          </span>
                          <p className="text-xs font-mono text-ink leading-relaxed">
                            {selectedCase.text}
                          </p>
                        </div>

                        {/* Detected Findings */}
                        <div>
                          <h3 className="text-xs font-semibold text-ink-soft mb-2">
                            Detected Findings ({selectedCase.detected_findings.length})
                          </h3>
                          <div className="space-y-2">
                            {selectedCase.detected_findings.map((f, idx) => (
                              <div
                                key={idx}
                                className="p-3 rounded-lg bg-paper border border-line text-xs flex flex-col gap-1"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-ink">{f.title}</span>
                                  <Badge
                                    variant="severity"
                                    value={f.severity}
                                    className="text-[11px]"
                                  />
                                </div>
                                {f.quoted && (
                                  <p className="text-ink-soft text-[11px]">
                                    Quoted: <span className="font-mono text-amber-300">&quot;{f.quoted}&quot;</span>
                                  </p>
                                )}
                                {f.source && (
                                  <p className="text-[11px] text-accent-ink">
                                    Source: {f.source}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Missed / False Negatives if any */}
                        {selectedCase.missed_expected.length > 0 && (
                          <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs">
                            <span className="font-semibold text-rose-400 block mb-1 flex items-center gap-1.5">
                              <AlertTriangle className="w-4 h-4" />
                              Missed Expected Violations (False Negatives)
                            </span>
                            <ul className="list-disc list-inside text-rose-300/80 space-y-1 text-[11px]">
                              {selectedCase.missed_expected.map((m, idx) => (
                                <li key={idx}>
                                  Expected type: <span className="font-mono font-semibold">{m.finding_type}</span> ({m.expected_match})
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </Card>
                    ) : (
                      <div className="p-8 text-center text-xs text-ink-mute">
                        Select a benchmark case on the left to inspect detailed telemetry.
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-xs text-ink-mute">Failed to load benchmark evaluation dataset.</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
