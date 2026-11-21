"use client";

import React, { useMemo } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  CheckCircle2,
  AlertTriangle,
  Award,
  Sparkles,
  Layers,
  ArrowRight,
  Sliders,
  Scale,
  FileSpreadsheet,
  BookOpen,
  Wrench,
  Check,
  FileCheck2,
  ExternalLink,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReviewDetail, Finding, Claim } from "@/lib/types";

interface EvaluationScorecardProps {
  review: ReviewDetail;
  onSelectTab: (tab: "findings" | "ledger" | "diff" | "activity" | "evidence") => void;
  onAcceptFix?: (finding: Finding) => void;
  onFilterSeverity?: (severity: string) => void;
  acceptingFixId?: string | null;
}

export function EvaluationScorecard({
  review,
  onSelectTab,
  onAcceptFix,
  onFilterSeverity,
  acceptingFixId,
}: EvaluationScorecardProps) {
  const findings = useMemo(() => review.findings || [], [review.findings]);
  const claims = useMemo(() => review.claims || [], [review.claims]);

  const openBlockers = useMemo(
    () =>
      findings.filter(
        (f) =>
          (f.severity === "Blocker" || f.severity === "Critical") &&
          (f.status === "Open" || (f.status as string) === "open")
      ),
    [findings]
  );

  const hasOpenBlockers = openBlockers.length > 0;

  // Grade & Score calculation
  const { grade, gradeLabel, scorePercent, scoreBadgeColor } = useMemo(() => {
    const rawRisk = review.risk_score || 0;

    if (hasOpenBlockers) {
      return {
        grade: "F",
        gradeLabel: "Publication Blocked",
        scorePercent: Math.max(35, Math.round(100 - rawRisk * 2)),
        scoreBadgeColor: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      };
    }

    if (rawRisk <= 5) {
      return {
        grade: "A+",
        gradeLabel: "Flawless Brand Governance",
        scorePercent: 98,
        scoreBadgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
      };
    }
    if (rawRisk <= 15) {
      return {
        grade: "A",
        gradeLabel: "Brand Compliant",
        scorePercent: 92,
        scoreBadgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
      };
    }
    if (rawRisk <= 35) {
      return {
        grade: "B",
        gradeLabel: "Minor Advisories",
        scorePercent: 82,
        scoreBadgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/40",
      };
    }
    if (rawRisk <= 60) {
      return {
        grade: "C",
        gradeLabel: "Remediation Needed",
        scorePercent: 68,
        scoreBadgeColor: "bg-orange-500/20 text-orange-300 border-orange-500/40",
      };
    }

    return {
      grade: "F",
      gradeLabel: "Critical Inconsistencies",
      scorePercent: 45,
      scoreBadgeColor: "bg-rose-500/20 text-rose-300 border-rose-500/40",
    };
  }, [review.risk_score, hasOpenBlockers]);

  // Category breakdown calculations
  const categories = useMemo(() => {
    // 1. Voice & Guidelines
    const voiceFindings = findings.filter(
      (f) =>
        f.source_type === "guideline" ||
        f.finding_type?.toLowerCase().includes("tone") ||
        f.finding_type?.toLowerCase().includes("voice") ||
        f.finding_type?.toLowerCase().includes("accessibility")
    );
    const voiceScore = Math.max(0, 100 - voiceFindings.length * 15);

    // 2. Legal & Regulatory
    const legalFindings = findings.filter(
      (f) =>
        f.source_type === "rule" ||
        f.finding_type?.toLowerCase().includes("disclaimer") ||
        f.finding_type?.toLowerCase().includes("legal") ||
        f.finding_type?.toLowerCase().includes("forbidden")
    );
    const legalScore = Math.max(0, 100 - legalFindings.length * 20);

    // 3. Factual Claims
    const factFindings = findings.filter(
      (f) =>
        f.source_type === "fact" ||
        f.finding_type?.toLowerCase().includes("numeric") ||
        f.finding_type?.toLowerCase().includes("expired")
    );
    const supportedClaims = claims.filter(
      (c) => c.status === "SUPPORTED" || c.status === "Verified"
    );
    const claimScore =
      claims.length > 0
        ? Math.round((supportedClaims.length / claims.length) * 100)
        : 100;

    // 4. Nomenclature & Terminology
    const termFindings = findings.filter(
      (f) =>
        f.source_type === "term" ||
        f.finding_type?.toLowerCase().includes("term") ||
        f.finding_type?.toLowerCase().includes("nomenclature")
    );
    const termScore = Math.max(0, 100 - termFindings.length * 15);

    return [
      {
        id: "voice",
        name: "Brand Voice & Guidelines",
        desc: "Tone consistency, stylistic adherence, and brand personality",
        score: voiceScore,
        violationsCount: voiceFindings.length,
        icon: Sliders,
      },
      {
        id: "legal",
        name: "Legal & Regulatory Guardrails",
        desc: "Mandatory disclaimers, required disclosures, and risk phrases",
        score: legalScore,
        violationsCount: legalFindings.length,
        icon: Scale,
      },
      {
        id: "claims",
        name: "Factual Claims Accuracy",
        desc: "Strict verification of metrics, statistics, and SLA claims",
        score: claimScore,
        violationsCount: factFindings.length,
        icon: FileSpreadsheet,
      },
      {
        id: "terms",
        name: "Nomenclature & Terminology",
        desc: "Canonical trademark naming and avoidance of deprecated terms",
        score: termScore,
        violationsCount: termFindings.length,
        icon: BookOpen,
      },
    ];
  }, [findings, claims]);

  // Key Strengths
  const strengths = useMemo(() => {
    const list: string[] = [];
    const supportedClaims = claims.filter(
      (c) => c.status === "SUPPORTED" || c.status === "Verified"
    );
    if (supportedClaims.length > 0) {
      list.push(
        `${supportedClaims.length} factual proposition${
          supportedClaims.length > 1 ? "s" : ""
        } strictly validated against canonical ground-truth facts.`
      );
    }

    const termFindings = findings.filter(
      (f) => f.source_type === "term" || f.finding_type?.includes("term")
    );
    if (termFindings.length === 0) {
      list.push("100% compliant brand nomenclature and trademark usage.");
    }

    const voiceFindings = findings.filter(
      (f) => f.source_type === "guideline" || f.finding_type?.includes("tone")
    );
    if (voiceFindings.length === 0) {
      list.push("Adheres fully to active voice tone and persona guidelines.");
    }

    if (list.length === 0) {
      list.push("Document successfully chunked and analyzed through CitationGate.");
    }

    return list;
  }, [claims, findings]);

  // Key Weaknesses & Blockers
  const weaknesses = useMemo(() => {
    const list: string[] = [];

    if (openBlockers.length > 0) {
      list.push(
        `${openBlockers.length} active blocker finding${
          openBlockers.length > 1 ? "s" : ""
        } preventing publication under organizational policy.`
      );
    }

    const conflicts = claims.filter(
      (c) => c.status === "CONFLICTS" || c.status === "Disputed"
    );
    if (conflicts.length > 0) {
      list.push(
        `${conflicts.length} claim${conflicts.length > 1 ? "s" : ""} contradict canonical facts on record.`
      );
    }

    const unsupported = claims.filter(
      (c) => c.status === "UNSUPPORTED" || c.status === "Proposed"
    );
    if (unsupported.length > 0) {
      list.push(
        `${unsupported.length} unverified claim${
          unsupported.length > 1 ? "s" : ""
        } lacking active cited source evidence.`
      );
    }

    const expired = claims.filter((c) => c.status === "EXPIRED");
    if (expired.length > 0) {
      list.push(`${expired.length} claim cites expired, historical facts.`);
    }

    return list;
  }, [openBlockers, claims]);

  // Actionable Recommendations
  const actionableFindings = useMemo(() => {
    return findings
      .filter((f) => (f.status === "Open" || (f.status as string) === "open") && (f.suggestion || f.suggested_replacement))
      .slice(0, 4);
  }, [findings]);

  // Unique evidence sources cited
  const evidenceSources = useMemo(() => {
    const set = new Map<string, { source: string; type: string; count: number }>();
    findings.forEach((f) => {
      if (f.source_reference) {
        const existing = set.get(f.source_reference);
        if (existing) {
          existing.count += 1;
        } else {
          set.set(f.source_reference, {
            source: f.source_reference,
            type: f.source_type || "Rule",
            count: 1,
          });
        }
      }
    });
    return Array.from(set.values()).slice(0, 6);
  }, [findings]);

  return (
    <div className="space-y-6">
      {/* Top Hero: Health Grade & Overall Scorecard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Overall Brand Grade Box */}
        <Card className="p-6 bg-surface border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
                Brand Health Grade
              </span>
              <span className={`text-xs font-bold font-mono px-2.5 py-0.5 rounded-full border ${scoreBadgeColor}`}>
                {gradeLabel}
              </span>
            </div>

            <div className="my-5 flex items-center gap-5">
              <div
                className={`w-20 h-20 rounded-2xl flex items-center justify-center font-bold text-4xl shadow-inner border ${
                  hasOpenBlockers
                    ? "bg-rose-500/15 text-rose-300 border-rose-500/40"
                    : grade.startsWith("A")
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/40"
                    : "bg-amber-500/15 text-amber-300 border-amber-500/40"
                }`}
              >
                {grade}
              </div>

              <div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-extrabold text-ink">{scorePercent}%</span>
                  <span className="text-xs text-ink-mute font-medium">Compliance</span>
                </div>
                <p className="text-xs text-ink-soft mt-1">
                  Risk Score: <strong className="text-ink">{review.risk_score || 0} pts</strong> ({review.risk_level || "Low"})
                </p>
                <p className="text-[11px] text-ink-mute mt-0.5">
                  {openBlockers.length} open blocker{openBlockers.length === 1 ? "" : "s"}
                </p>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-line flex items-center justify-between text-xs">
            <span className="text-ink-mute">Evaluation Standard:</span>
            <span className="text-accent-ink font-semibold">CitationGate v2.4</span>
          </div>
        </Card>

        {/* 4 Category Breakdown Progress Bars */}
        <Card className="p-6 bg-surface border-line lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-line">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-soft flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-accent-ink" />
              Governance Category Breakdown
            </h3>
            <span className="text-[11px] text-ink-mute">Based on active brand knowledge</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isGood = cat.score >= 80;
              const isWarning = cat.score >= 60 && cat.score < 80;

              return (
                <div
                  key={cat.id}
                  className="p-3 rounded-lg bg-paper border border-line space-y-2 hover:border-line-strong transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-ink flex items-center gap-1.5">
                      <Icon className="w-3.5 h-3.5 text-accent-ink shrink-0" />
                      <span className="truncate">{cat.name}</span>
                    </span>
                    <span
                      className={`text-xs font-bold font-mono ${
                        isGood ? "text-emerald-400" : isWarning ? "text-amber-400" : "text-rose-400"
                      }`}
                    >
                      {cat.score}%
                    </span>
                  </div>

                  <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-500 ${
                        isGood ? "bg-emerald-400" : isWarning ? "bg-amber-400" : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.max(5, cat.score)}%` }}
                    />
                  </div>

                  <p className="text-[10px] text-ink-mute line-clamp-1">
                    {cat.violationsCount > 0 ? (
                      <span className="text-amber-400 font-medium">
                        {cat.violationsCount} flagged finding{cat.violationsCount > 1 ? "s" : ""}
                      </span>
                    ) : (
                      "Zero violations detected"
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Strengths & Weaknesses Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Strengths Card */}
        <Card className="p-5 bg-surface border-line space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-line text-xs font-semibold text-emerald-400">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Key Brand Strengths</span>
          </div>

          <ul className="space-y-2 text-xs">
            {strengths.map((s, idx) => (
              <li key={idx} className="flex items-start gap-2 text-ink-soft">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                <span className="leading-relaxed">{s}</span>
              </li>
            ))}
          </ul>
        </Card>

        {/* Weaknesses & Blockers Card */}
        <Card className="p-5 bg-surface border-line space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-line text-xs font-semibold">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              <span>Key Weaknesses & Blockers</span>
            </div>
            {openBlockers.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onSelectTab("findings");
                  if (onFilterSeverity) onFilterSeverity("blocker");
                }}
                className="text-[11px] h-6 px-2 text-rose-400 border-rose-800 hover:bg-rose-950/40"
              >
                Inspect Blockers ({openBlockers.length})
              </Button>
            )}
          </div>

          <ul className="space-y-2 text-xs">
            {weaknesses.length > 0 ? (
              weaknesses.map((w, idx) => (
                <li key={idx} className="flex items-start gap-2 text-rose-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                  <span className="leading-relaxed">{w}</span>
                </li>
              ))
            ) : (
              <li className="text-ink-mute text-xs flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                No critical blockers or severe contradictions detected.
              </li>
            )}
          </ul>
        </Card>
      </div>

      {/* Actionable Recommendations with Direct Remediation */}
      {actionableFindings.length > 0 && (
        <Card className="p-5 bg-surface border-line space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-line">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Wrench className="w-4 h-4 text-accent-ink" />
              <span>Actionable Remediation Recommendations</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelectTab("findings")}
              className="text-xs text-accent-ink border-line-strong hover:bg-sunken h-7"
            >
              View All Findings ({findings.length})
              <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {actionableFindings.map((f) => (
              <div
                key={f.id}
                className="p-3.5 rounded-lg bg-paper border border-line space-y-2.5 hover:border-line-strong transition-all"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink truncate">
                    {f.title || f.finding_type}
                  </span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      f.severity === "Blocker"
                        ? "border-rose-500/40 text-rose-400 bg-rose-500/10"
                        : "border-amber-500/40 text-amber-400 bg-amber-500/10"
                    }`}
                  >
                    {f.severity}
                  </Badge>
                </div>

                {f.quoted_text && (
                  <div className="p-2 rounded bg-sunken text-[11px] font-mono text-rose-300 line-clamp-2">
                    &ldquo;{f.quoted_text}&rdquo;
                  </div>
                )}

                <p className="text-xs text-ink-soft leading-relaxed">
                  {f.suggestion || f.message}
                </p>

                {f.suggested_replacement && onAcceptFix && (
                  <div className="pt-2 border-t border-line flex items-center justify-between">
                    <span className="text-[10px] text-ink-mute truncate max-w-[180px]">
                      Suggested: <strong className="text-emerald-400 font-mono">{f.suggested_replacement}</strong>
                    </span>
                    <Button
                      size="sm"
                      onClick={() => onAcceptFix(f)}
                      isLoading={acceptingFixId === f.id}
                      className="bg-accent hover:bg-accent-hover text-ink text-[11px] h-6 px-2 font-semibold"
                    >
                      Accept Fix
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Evidence Source Linkage */}
      {evidenceSources.length > 0 && (
        <Card className="p-5 bg-surface border-line space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-line">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <FileCheck2 className="w-4 h-4 text-accent-ink" />
              <span>Evidence Source Traceability Linkage</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelectTab("evidence")}
              className="text-xs text-ink border-line-strong hover:bg-sunken h-7"
            >
              Evidence Manager
              <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {evidenceSources.map((ev, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded-lg bg-paper border border-line flex items-center justify-between text-xs"
              >
                <div className="overflow-hidden">
                  <span className="font-mono text-accent-ink font-semibold truncate block">
                    {ev.source}
                  </span>
                  <span className="text-[10px] text-ink-mute block uppercase">
                    Type: {ev.type}
                  </span>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono text-emerald-400 border-emerald-500/30">
                  Verified
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
