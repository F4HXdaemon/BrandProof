"use client";

import React, { useState, useEffect } from "react";
import {
  Target,
  Play,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  ShieldCheck,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { EvaluationResult, EvaluationCase } from "@/lib/types";

export default function EvaluationPage() {
  const { error } = useToast();
  const [data, setData] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [selectedCase, setSelectedCase] = useState<EvaluationCase | null>(null);

  const loadEvaluation = async () => {
    setRunning(true);
    try {
      const res = await api.evaluation.run();
      setData(res);
      if (res.cases.length > 0) {
        setSelectedCase(res.cases[0]);
      }
    } catch (err) {
      console.error("Evaluation run failed:", err);
    } finally {
      setLoading(false);
      setRunning(false);
    }
  };

  useEffect(() => {
    loadEvaluation();
  }, []);

  const handleExportCsv = async () => {
    try {
      await api.evaluation.downloadCsv();
    } catch (err: any) {
      console.error("Export CSV failed:", err);
      error("Export Failed", err.message || "Failed to download evaluation CSV.");
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">
                Evaluation
              </h1>
            <p className="text-xs text-ink-soft mt-1">
              Precision, recall and F1 of the rule engine against the benchmark cases.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
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
              onClick={loadEvaluation}
              disabled={running}
              className="text-xs bg-accent hover:bg-accent-hover text-ink font-medium"
            >
              <Play className={`w-3.5 h-3.5 mr-1.5 ${running ? "animate-spin" : ""}`} />
              {running ? "Running Benchmark..." : "Re-Run Benchmark"}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
            <Skeleton className="h-96 w-full" />
          </div>
        ) : data ? (
          <>
            {/* Top Score Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-4 bg-surface border-line">
                <span className="text-xs font-semibold text-ink-soft">Precision</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-emerald-400">
                    {(data.metrics.precision * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-[11px] text-ink-mute mt-1">
                  TP / (TP + FP) — Low false alarm rate
                </p>
              </Card>

              <Card className="p-4 bg-surface border-line">
                <span className="text-xs font-semibold text-ink-soft">Recall</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-accent-ink">
                    {(data.metrics.recall * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-[11px] text-ink-mute mt-1">
                  TP / (TP + FN) — High violation capture
                </p>
              </Card>

              <Card className="p-4 bg-surface border-line">
                <span className="text-xs font-semibold text-ink-soft">F1 Score</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-ink">
                    {data.metrics.f1_score.toFixed(3)}
                  </span>
                </div>
                <p className="text-[11px] text-ink-mute mt-1">
                  Harmonic mean of precision and recall
                </p>
              </Card>

              <Card className="p-4 bg-surface border-line">
                <span className="text-xs font-semibold text-ink-soft">Detection Accuracy</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-emerald-400">
                    {data.metrics.accuracy_percent}%
                  </span>
                </div>
                <p className="text-[11px] text-ink-mute mt-1">
                  {data.metrics.true_positives} TP · {data.metrics.false_positives} FP · {data.metrics.false_negatives} FN
                </p>
              </Card>
            </div>

            {/* Split View: Test Cases List & Case Detail */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Cases List */}
              <div className="lg:col-span-5 space-y-3">
                <div className="flex items-center justify-between text-xs text-ink-soft px-1 font-semibold">
                  <span>Benchmark Cases ({data.cases.length})</span>
                  <span>Status</span>
                </div>

                <div className="space-y-2">
                  {data.cases.map((c) => {
                    const isSelected = selectedCase?.case_id === c.case_id;
                    const isPass = c.false_negatives === 0 && c.false_positives === 0;

                    return (
                      <div
                        key={c.case_id}
                        onClick={() => setSelectedCase(c)}
                        className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? "bg-accent-soft border-accent  "
                            : "bg-surface border-line hover:border-line-strong"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-ink truncate">{c.title}</span>
                          {isPass ? (
                            <Badge variant="outline" className="text-[11px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              PASS
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[11px] bg-amber-500/10 text-amber-400 border-amber-500/20">
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
                      <h3 className="text-xs font-semibold text-ink text-ink-soft mb-2">
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
    </AppShell>
  );
}
