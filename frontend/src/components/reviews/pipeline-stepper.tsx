"use client";

import React from "react";
import {
  FileText,
  Sliders,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  RefreshCw,
  Clock,
  Layers,
} from "lucide-react";
import { ReviewDetail } from "@/lib/types";

interface PipelineStepperProps {
  review: ReviewDetail;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export function PipelineStepper({ review, onRetry, isRetrying }: PipelineStepperProps) {
  const isFailed = review.processing_status === "Failed";
  const isProcessing =
    review.processing_status === "Processing" ||
    review.processing_status === "Extracting" ||
    review.processing_status === "Submitting";

  const hasBlockers = (review.findings || []).some(
    (f) =>
      (f.severity === "Blocker" || f.severity === "Critical") &&
      (f.status === "Open" || (f.status as string) === "open")
  );

  const stages = [
    {
      id: "ingestion",
      name: "1. Ingestion & Chunking",
      desc: review.document_title || "Document parsed into structural paragraphs",
      icon: FileText,
      status: "completed",
    },
    {
      id: "rules",
      name: "2. Voice & Rule Engine",
      desc: "Deterministic brand rules & guideline checks",
      icon: Sliders,
      status: "completed",
    },
    {
      id: "claims",
      name: "3. Claim Extraction",
      desc: `${review.claims?.length || 0} factual propositions extracted`,
      icon: Sparkles,
      status: "completed",
    },
    {
      id: "citation",
      name: "4. CitationGate Gatekeeper",
      desc: "Canonical source validation & truth matching",
      icon: ShieldCheck,
      status: isFailed ? "failed" : isProcessing ? "processing" : "completed",
    },
    {
      id: "scoring",
      name: "5. Risk Telemetry",
      desc: hasBlockers ? "Publication Blocked" : "Ready for Approval",
      icon: hasBlockers ? AlertOctagon : CheckCircle2,
      status: isFailed
        ? "failed"
        : isProcessing
        ? "pending"
        : hasBlockers
        ? "warning"
        : "completed",
    },
  ];

  return (
    <div className="p-4 rounded-xl bg-surface border border-line space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-line">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-accent-ink" />
          <span className="text-xs font-semibold text-ink">Governance Pipeline Telemetry</span>
          <span className="text-[10px] text-ink-mute font-mono">
            CitationGate v2.4
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          {isProcessing ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-accent-soft text-accent-ink font-medium text-[11px] animate-pulse">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Scan in progress
            </span>
          ) : isFailed ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 font-medium text-[11px] border border-rose-500/30">
              <AlertOctagon className="w-3 h-3 text-rose-400" />
              Pipeline Failed
            </span>
          ) : hasBlockers ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 font-medium text-[11px] border border-rose-500/30">
              <AlertOctagon className="w-3 h-3 text-rose-400" />
              Publication Locked (Blockers Found)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 font-medium text-[11px] border border-emerald-500/30">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              All Stages Verified Clean
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5">
        {stages.map((stage, idx) => {
          const Icon = stage.icon;
          const isDone = stage.status === "completed";
          const isWarn = stage.status === "warning";
          const isErr = stage.status === "failed";
          const isProc = stage.status === "processing";

          return (
            <div
              key={stage.id}
              className={`p-2.5 rounded-lg border transition-all ${
                isErr
                  ? "bg-rose-950/30 border-rose-800 text-rose-200"
                  : isWarn
                  ? "bg-rose-950/20 border-rose-800/60 text-rose-200"
                  : isProc
                  ? "bg-accent-soft/30 border-accent/40 text-ink"
                  : isDone
                  ? "bg-paper border-line text-ink"
                  : "bg-sunken border-line/50 text-ink-mute"
              }`}
            >
              <div className="flex items-center justify-between pb-1">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    isErr
                      ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                      : isWarn
                      ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                      : isProc
                      ? "bg-accent text-ink"
                      : isDone
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                      : "bg-sunken text-ink-mute"
                  }`}
                >
                  {isDone ? (
                    "✓"
                  ) : isErr || isWarn ? (
                    "!"
                  ) : isProc ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    idx + 1
                  )}
                </div>
                <Icon
                  className={`w-3.5 h-3.5 ${
                    isErr || isWarn
                      ? "text-rose-400"
                      : isDone
                      ? "text-emerald-400"
                      : isProc
                      ? "text-accent-ink animate-spin"
                      : "text-ink-mute"
                  }`}
                />
              </div>

              <span className="block text-xs font-semibold truncate text-ink">
                {stage.name}
              </span>
              <span className="block text-[10px] text-ink-mute truncate mt-0.5">
                {stage.desc}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
