"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ShieldAlert,
  AlertOctagon,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  UserCheck,
  Send,
  ExternalLink,
  MessageSquare,
  Download,
  Layers,
  FileCode,
  Tag,
  Globe,
  Sliders,
  Compass,
  FileSpreadsheet,
  Copy,
  Check,
  GitCommit,
  GitPullRequest,
  Split,
  RefreshCw,
  Filter,
  Clock,
  Lock,
  Unlock,
  FileDiff,
  HelpCircle,
  CheckCheck,
  ArrowRight,
  Shield,
  Info,
  CornerDownRight,
  FileCheck2,
  Paperclip,
  Unlink,
  Plus,
  Upload,
  X,
  AlertCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import {
  ReviewDetail,
  Document,
  DocumentChunk,
  Finding,
  Claim,
  DiffResult,
  Comment,
  Evidence,
} from "@/lib/types";
import { formatDate, formatRelativeTime, formatBytes, getEvidenceStatusBadge } from "@/lib/utils";
import { PipelineStepper } from "@/components/reviews/pipeline-stepper";
import { EvaluationScorecard } from "@/components/reviews/evaluation-scorecard";

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reviewId = params?.id as string;
  const { user } = useAuth();
  const { success, error, info } = useToast();

  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [docData, setDocData] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [diffData, setDiffData] = useState<DiffResult | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [diffLoading, setDiffLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [copiedText, setCopiedText] = useState(false);
  const [reEvaluating, setReEvaluating] = useState(false);
  const [copiedEvalId, setCopiedEvalId] = useState(false);

  // Active Tab
  const [activeTab, setActiveTab] = useState<"overview" | "findings" | "ledger" | "diff" | "activity" | "evidence">("overview");

  // Filter States
  const [findingSeverityFilter, setFindingSeverityFilter] = useState<string>("all");
  const [findingStatusFilter, setFindingStatusFilter] = useState<string>("all");
  const [claimStatusFilter, setClaimStatusFilter] = useState<string>("all");
  const [diffViewMode, setDiffViewMode] = useState<"inline" | "side-by-side">("inline");

  // Fix & Remediation State
  const [acceptingFixId, setAcceptingFixId] = useState<string | null>(null);

  // Dismiss Modal State
  const [dismissModalOpen, setDismissModalOpen] = useState(false);
  const [dismissFinding, setDismissFinding] = useState<Finding | null>(null);
  const [dismissReason, setDismissReason] = useState("");
  const [dismissing, setDismissing] = useState(false);

  // Approval / Override Modal State
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [isOverrideMode, setIsOverrideMode] = useState(false);
  const [approvalComments, setApprovalComments] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [submittingApproval, setSubmittingApproval] = useState(false);

  // Request Changes Modal State
  const [changesModalOpen, setChangesModalOpen] = useState(false);
  const [changesComments, setChangesComments] = useState("");
  const [submittingChanges, setSubmittingChanges] = useState(false);

  // New Comment Form State
  const [newCommentText, setNewCommentText] = useState("");
  const [newCommentFindingId, setNewCommentFindingId] = useState<string>("");
  const [submittingComment, setSubmittingComment] = useState(false);

  const fetchDiff = useCallback(async (baseVerId?: string) => {
    if (!reviewId) return;
    setDiffLoading(true);
    try {
      const diff = await api.reviews.getDiff(reviewId, baseVerId);
      setDiffData(diff);
    } catch (dErr) {
      console.warn("No diff available or single version present", dErr);
    } finally {
      setDiffLoading(false);
    }
  }, [reviewId]);

  const fetchReview = useCallback(async () => {
    if (!reviewId) return;
    setLoading(true);
    try {
      const rev = await api.reviews.get(reviewId);
      setReview(rev);
      if (rev.document_id) {
        const doc = await api.documents.get(rev.document_id);
        setDocData(doc);

        try {
          const fetchedChunks = await api.documents.getChunks(rev.document_id, rev.version_id);
          setChunks(fetchedChunks);
        } catch (cErr) {
          console.error("Failed to fetch document chunks", cErr);
        }
      }

      // Fetch comments
      try {
        const fetchedComments = await api.reviews.getComments(reviewId);
        setComments(fetchedComments);
      } catch (comErr) {
        console.error("Failed to fetch comments", comErr);
      }

      // Pre-fetch diff
      fetchDiff();
    } catch (err: any) {
      error("Error loading review", err.message || "Failed to fetch review details");
    } finally {
      setLoading(false);
    }
  }, [reviewId, fetchDiff, error]);

  useEffect(() => {
    fetchReview();
  }, [fetchReview]);

  // Automated background polling while evaluation is in progress
  const processingStatus = review?.processing_status;
  useEffect(() => {
    if (!processingStatus) return;
    const isProcessing =
      processingStatus === "Processing" ||
      processingStatus === "Extracting" ||
      processingStatus === "Submitting";

    if (isProcessing) {
      const interval = setInterval(() => {
        fetchReview();
      }, 2500);
      return () => clearInterval(interval);
    }
  }, [processingStatus, fetchReview]);

  const handleReEvaluate = async () => {
    if (!reviewId || reEvaluating) return;
    setReEvaluating(true);
    try {
      const updated = await api.reviews.reEvaluate(reviewId);
      setReview(updated);
      success("Evaluation Completed", "Review re-evaluated against current applicable knowledge.");
      await fetchReview();
    } catch (err: any) {
      error("Evaluation Failed", err.message || "Failed to re-evaluate review.");
    } finally {
      setReEvaluating(false);
    }
  };

  // Permissions & Blocker Calculations
  const isReviewerOrAdmin =
    user?.role === "Reviewer" ||
    user?.role === "Brand Manager" ||
    user?.role === "Admin";

  const isBrandManagerOrAdmin =
    user?.role === "Brand Manager" || user?.role === "Admin";

  const openBlockers = useMemo(() => {
    if (!review?.findings) return [];
    return review.findings.filter(
      (f) =>
        (f.severity === "Blocker" || f.severity === "Critical") &&
        (f.status === "Open" || (f.status as string) === "open")
    );
  }, [review?.findings]);

  const hasOpenBlockers = openBlockers.length > 0;

  // Breakdown metrics
  const findingCounts = useMemo(() => {
    const list = review?.findings || [];
    return {
      total: list.length,
      blocker: list.filter((f) => f.severity === "Blocker" || f.severity === "Critical").length,
      high: list.filter((f) => f.severity === "High").length,
      warning: list.filter((f) => f.severity === "Warning" || f.severity === "Medium").length,
      info: list.filter((f) => f.severity === "Info" || f.severity === "Low").length,
      open: list.filter((f) => f.status === "Open").length,
      resolved: list.filter((f) => f.status === "Resolved" || f.status === "Fixed" || f.status === "Dismissed").length,
    };
  }, [review?.findings]);

  const claimCounts = useMemo(() => {
    const list = review?.claims || [];
    return {
      total: list.length,
      supported: list.filter((c) => c.status === "SUPPORTED" || c.status === "Verified").length,
      conflicts: list.filter((c) => c.status === "CONFLICTS" || c.status === "Disputed").length,
      expired: list.filter((c) => c.status === "EXPIRED").length,
      out_of_scope: list.filter((c) => c.status === "OUT_OF_SCOPE").length,
      unsupported: list.filter((c) => c.status === "UNSUPPORTED" || c.status === "Unverified" || c.status === "Proposed").length,
    };
  }, [review?.claims]);

  // Filtered Findings
  const filteredFindings = useMemo(() => {
    let list = review?.findings || [];
    if (findingSeverityFilter !== "all") {
      if (findingSeverityFilter === "blocker") {
        list = list.filter((f) => f.severity === "Blocker" || f.severity === "Critical");
      } else if (findingSeverityFilter === "high") {
        list = list.filter((f) => f.severity === "High");
      } else if (findingSeverityFilter === "warning") {
        list = list.filter((f) => f.severity === "Warning" || f.severity === "Medium");
      } else if (findingSeverityFilter === "info") {
        list = list.filter((f) => f.severity === "Info" || f.severity === "Low");
      }
    }
    if (findingStatusFilter !== "all") {
      if (findingStatusFilter === "open") {
        list = list.filter((f) => f.status === "Open");
      } else if (findingStatusFilter === "resolved") {
        list = list.filter((f) => f.status === "Resolved" || f.status === "Fixed");
      } else if (findingStatusFilter === "dismissed") {
        list = list.filter((f) => f.status === "Dismissed" || f.status === "Waived");
      }
    }
    return list;
  }, [review?.findings, findingSeverityFilter, findingStatusFilter]);

  // Filtered Claims
  const filteredClaims = useMemo(() => {
    let list = review?.claims || [];
    if (claimStatusFilter !== "all") {
      list = list.filter((c) => c.status === claimStatusFilter);
    }
    return list;
  }, [review?.claims, claimStatusFilter]);

  // Handle Accepting Fix
  const handleAcceptFix = async (finding: Finding) => {
    if (!review) return;
    setAcceptingFixId(finding.id);
    try {
      const updatedReview = await api.reviews.acceptFix(review.id, finding.id);
      success(
        "Remediation Applied",
        `Version ${updatedReview.version?.version_number || 2} generated with accepted fix. Content re-audited!`
      );
      setReview(updatedReview);
      await fetchReview();
      setActiveTab("diff");
    } catch (err: any) {
      error("Failed to Accept Fix", err.message || "Could not apply remediation.");
    } finally {
      setAcceptingFixId(null);
    }
  };

  // Open Dismiss Modal
  const openDismissModal = (finding: Finding) => {
    setDismissFinding(finding);
    setDismissReason("");
    setDismissModalOpen(true);
  };

  // Confirm Dismissal
  const handleConfirmDismiss = async () => {
    if (!review || !dismissFinding) return;
    if (!dismissReason.trim()) {
      error("Validation Error", "A business justification is mandatory to dismiss a governance finding.");
      return;
    }
    setDismissing(true);
    try {
      await api.reviews.dismissFinding(review.id, dismissFinding.id, dismissReason.trim());
      success(
        "Finding Dismissed",
        "Finding status updated to Dismissed and logged in compliance audit trail."
      );
      setDismissModalOpen(false);
      setDismissFinding(null);
      fetchReview();
    } catch (err: any) {
      error("Dismissal Failed", err.message || "Could not dismiss finding.");
    } finally {
      setDismissing(false);
    }
  };

  // Handle Human Approval Submission
  const handleConfirmApproval = async () => {
    if (!review) return;
    if (isOverrideMode && (!overrideReason || overrideReason.trim().length < 10)) {
      error("Validation Error", "An explicit business justification of at least 10 characters is required for Blocker override.");
      return;
    }

    setSubmittingApproval(true);
    try {
      await api.approvals.recordDecision(review.id, {
        status: "Approved",
        comments: approvalComments.trim() || (isOverrideMode ? `Blocker Override: ${overrideReason.trim()}` : "Publication approved by authorized reviewer."),
        is_override: isOverrideMode,
        override_reason: isOverrideMode ? overrideReason.trim() : undefined,
      });

      success(
        isOverrideMode ? "Blockers Overridden & Approved" : "Publication Approved",
        isOverrideMode
          ? "Authorized override executed. Audit trail updated with compliance rationale."
          : "Draft cleared for distribution. Audit trail updated."
      );
      setApprovalModalOpen(false);
      setApprovalComments("");
      setOverrideReason("");
      fetchReview();
    } catch (err: any) {
      error("Approval Failed", err.message || "Failed to record approval decision.");
    } finally {
      setSubmittingApproval(false);
    }
  };

  // Handle Request Changes Submission
  const handleConfirmChanges = async () => {
    if (!review) return;
    if (!changesComments.trim()) {
      error("Validation Error", "Please provide detailed revision instructions for the creator.");
      return;
    }

    setSubmittingChanges(true);
    try {
      await api.approvals.recordDecision(review.id, {
        status: "Changes Requested",
        comments: changesComments.trim(),
      });
      success("Changes Requested", "Status updated and author notified with revision instructions.");
      setChangesModalOpen(false);
      setChangesComments("");
      fetchReview();
    } catch (err: any) {
      error("Action Failed", err.message || "Failed to request changes.");
    } finally {
      setSubmittingChanges(false);
    }
  };

  // Add Comment
  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!review || !newCommentText.trim()) return;
    setSubmittingComment(true);
    try {
      const added = await api.reviews.addComment(
        review.id,
        newCommentText.trim(),
        newCommentFindingId || undefined
      );
      setComments((prev) => [...prev, added]);
      setNewCommentText("");
      setNewCommentFindingId("");
      success("Comment Added", "Comment logged to governance timeline.");
    } catch (err: any) {
      error("Failed to Post Comment", err.message || "Could not save comment.");
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleDownload = async () => {
    if (!docData) return;
    setDownloading(true);
    try {
      await api.documents.download(docData.id, docData.filename);
      success("Download Started", `Downloaded ${docData.filename}`);
    } catch (err: any) {
      error("Download Failed", err.message || "Failed to download original document.");
    } finally {
      setDownloading(false);
    }
  };

  const [downloadingReport, setDownloadingReport] = useState(false);
  const [attachEvidenceModalOpen, setAttachEvidenceModalOpen] = useState(false);
  const [availableEvidence, setAvailableEvidence] = useState<Evidence[]>([]);
  const [selectedAttachEvidenceId, setSelectedAttachEvidenceId] = useState("");
  const [linkingEvidence, setLinkingEvidence] = useState(false);
  const [exportingJson, setExportingJson] = useState(false);

  // Claim Evidence Link Modal State
  const [claimLinkModalOpen, setClaimLinkModalOpen] = useState(false);
  const [targetClaim, setTargetClaim] = useState<Claim | null>(null);
  const [selectedClaimEvidenceId, setSelectedClaimEvidenceId] = useState("");
  const [claimLinkReasoning, setClaimLinkReasoning] = useState("");
  const [linkingClaimEvidence, setLinkingClaimEvidence] = useState(false);

  const handleDownloadReport = async () => {
    if (!review) return;
    setDownloadingReport(true);
    try {
      const cleanTitle = (review.title || review.document_title || "evaluation")
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, "_");
      const filename = `${cleanTitle}_audit_report.pdf`;
      await api.reviews.downloadReport(review.id, filename);
      success("Report Downloaded", `Saved publication audit report: ${filename}`);
    } catch (err: any) {
      error("Report Failed", err.message || "Failed to generate evaluation audit report.");
    } finally {
      setDownloadingReport(false);
    }
  };

  const handleExportReportJson = async () => {
    if (!review) return;
    setExportingJson(true);
    try {
      const data = await api.reviews.getReportJson(review.id);
      const cleanTitle = (review.title || review.document_title || "evaluation")
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, "_");
      const filename = `${cleanTitle}_audit_report.json`;
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      success("JSON Report Exported", `Saved audit telemetry: ${filename}`);
    } catch (err: any) {
      error("Export Failed", err.message || "Failed to export JSON report.");
    } finally {
      setExportingJson(false);
    }
  };

  const handleOpenClaimLinkModal = async (claim: Claim) => {
    setTargetClaim(claim);
    setSelectedClaimEvidenceId(claim.evidence_id || "");
    setClaimLinkReasoning(claim.reasoning || "");
    setClaimLinkModalOpen(true);
    try {
      const allEv = await api.evidence.list();
      setAvailableEvidence(allEv);
    } catch (err) {
      console.warn("Could not load evidence for claim link", err);
    }
  };

  const handleConfirmClaimLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetClaim || !selectedClaimEvidenceId) {
      error("Selection Required", "Please choose an evidence document to back this claim.");
      return;
    }
    setLinkingClaimEvidence(true);
    try {
      await api.claims.linkEvidence(
        targetClaim.id,
        selectedClaimEvidenceId,
        "SUPPORTED",
        claimLinkReasoning.trim() || undefined
      );
      success("Evidence Linked to Claim", "Claim verified and CitationGate status updated to SUPPORTED.");
      setClaimLinkModalOpen(false);
      setTargetClaim(null);
      setSelectedClaimEvidenceId("");
      setClaimLinkReasoning("");
      fetchReview();
    } catch (err: any) {
      error("Link Failed", err.message || "Failed to link evidence to claim.");
    } finally {
      setLinkingClaimEvidence(false);
    }
  };

  const handleUnlinkClaimEvidence = async (claimId: string) => {
    if (!confirm("Are you sure you want to unlink evidence from this claim?")) return;
    try {
      await api.claims.unlinkEvidence(claimId);
      success("Evidence Unlinked", "Claim evidence removed and verification status updated.");
      fetchReview();
    } catch (err: any) {
      error("Failed to Unlink", err.message || "Could not unlink evidence.");
    }
  };

  const handleOpenAttachModal = async () => {
    setAttachEvidenceModalOpen(true);
    try {
      const allEv = await api.evidence.list();
      const alreadyLinkedIds = new Set((review?.evidence_documents || []).map((e: any) => e.id));
      setAvailableEvidence(allEv.filter((e) => !alreadyLinkedIds.has(e.id)));
    } catch (err) {
      console.warn("Could not load available evidence", err);
    }
  };

  const handleAttachEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!review || !selectedAttachEvidenceId) return;
    setLinkingEvidence(true);
    try {
      await api.evidence.associate(selectedAttachEvidenceId, review.id);
      success("Evidence Attached", "Corporate evidence document linked to this evaluation.");
      setAttachEvidenceModalOpen(false);
      setSelectedAttachEvidenceId("");
      fetchReview();
    } catch (err: any) {
      error("Link Failed", err.message || "Could not link evidence document.");
    } finally {
      setLinkingEvidence(false);
    }
  };

  const handleUnlinkEvidence = async (evidenceId: string) => {
    if (!review) return;
    if (!confirm("Are you sure you want to unlink this evidence document from this evaluation?")) return;
    try {
      await api.evidence.removeAssociation(evidenceId, review.id);
      success("Evidence Unlinked", "Evidence unlinked from this evaluation.");
      fetchReview();
    } catch (err: any) {
      error("Unlink Failed", err.message || "Could not unlink evidence.");
    }
  };

  const handleCopyRaw = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-48" />
            </div>
            <div className="flex gap-2">
              <Skeleton className="h-9 w-36" />
              <Skeleton className="h-9 w-36" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
          <Skeleton className="h-96 w-full" />
        </div>
      </AppShell>
    );
  }

  if (!review) {
    return (
      <AppShell>
        <div className="max-w-xl mx-auto py-16 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mx-auto text-rose-400">
            <AlertOctagon className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-semibold text-ink">Review Not Found</h2>
          <p className="text-sm text-ink-soft">
            The requested evaluation could not be loaded or you do not have permission to view it.
          </p>
          <div className="pt-2">
            <Link href="/reviews">
              <Button variant="outline" size="sm" className="gap-2">
                <ArrowLeft className="w-4 h-4" />
                Return to Reviews
              </Button>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const currentVersionNumber = review?.version?.version_number || 1;
  const currentExtractedText =
    review?.version?.extracted_text ||
    docData?.versions?.[0]?.extracted_text ||
    "Draft text not available.";

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Top Breadcrumb & Actions Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-1.5">
            <Link
              href="/reviews"
              className="inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Reviews</span>
            </Link>

            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                {review?.title || docData?.title || review?.document_title || "Document Review"}
              </h1>

              {/* Version Pill */}
              <span className="text-xs font-mono font-semibold px-2.5 py-0.5 rounded-full bg-accent-soft text-accent-ink border border-accent/30">
                v{currentVersionNumber}
              </span>

              {/* Status Badge */}
              {review && <Badge variant="status" value={review.status} />}

              {/* Transparent Risk Score Pill */}
              {review && (
                <div
                  className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full border ${
                    review.risk_level === "Critical"
                      ? "bg-rose-500/15 text-rose-300 border-rose-500/40"
                      : review.risk_level === "High"
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/40"
                      : review.risk_level === "Medium"
                      ? "bg-yellow-500/15 text-yellow-300 border-yellow-500/40"
                      : "bg-emerald-500/15 text-emerald-300 border-emerald-500/40"
                  }`}
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>
                    Risk Score: {review.risk_score || 0} • {review.risk_level || "Low"} Risk
                  </span>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
              <span>Document: <strong className="text-ink font-mono">{docData?.filename || review?.title}</strong></span>
              <span>•</span>
              <span>Author: <strong className="text-ink">{review?.creator_name || "Enterprise Author"}</strong></span>
              <span>•</span>
              <span>Evaluation ID: <code className="text-accent-ink font-mono bg-sunken px-1.5 py-0.5 rounded text-[11px]">{review?.id}</code></span>
              <button
                type="button"
                onClick={() => {
                  if (review?.id) {
                    navigator.clipboard.writeText(review.id);
                    setCopiedEvalId(true);
                    setTimeout(() => setCopiedEvalId(false), 2000);
                  }
                }}
                className="hover:text-ink text-ink-mute inline-flex items-center gap-1 text-[11px] transition-colors"
                title="Copy Evaluation ID"
              >
                {copiedEvalId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedEvalId ? "Copied" : "Copy ID"}</span>
              </button>
              <span>•</span>
              <span>Updated {formatRelativeTime(review?.updated_at)}</span>
            </div>
          </div>

          {/* Action Buttons for Human Approval Workflow */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Re-run Evaluation Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleReEvaluate}
              isLoading={reEvaluating}
              className="border-line-strong hover:bg-sunken text-xs font-medium text-ink bg-paper shadow-sm"
              title="Re-run brand governance evaluation against updated knowledge base"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 text-accent-ink ${reEvaluating ? "animate-spin" : ""}`} />
              Re-run Audit
            </Button>

            {/* Download Publication Audit Report (PDF) */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadReport}
              isLoading={downloadingReport}
              className="border-line-strong hover:bg-sunken text-xs font-medium text-ink bg-paper shadow-sm"
              title="Download formal publication compliance report (PDF)"
            >
              <Download className="w-3.5 h-3.5 mr-1.5 text-accent-ink" />
              Download Audit Report
            </Button>

            {/* Export Structured JSON Report */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportReportJson}
              isLoading={exportingJson}
              className="border-line-strong hover:bg-sunken text-xs font-medium text-ink bg-paper shadow-sm"
              title="Export structured JSON audit telemetry and evidence trail"
            >
              <FileCode className="w-3.5 h-3.5 mr-1.5 text-purple-400" />
              Export JSON
            </Button>

            {isReviewerOrAdmin ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setChangesModalOpen(true)}
                  className="border-line-strong hover:bg-sunken text-xs"
                >
                  <AlertTriangle className="w-3.5 h-3.5 mr-1.5 text-amber-400" />
                  Request Changes
                </Button>

                {hasOpenBlockers ? (
                  <>
                    {/* If open blockers, regular approve is blocked */}
                    <div className="relative group">
                      <Button
                        size="sm"
                        disabled
                        className="bg-sunken border border-line-strong text-ink-mute cursor-not-allowed text-xs"
                      >
                        <Lock className="w-3.5 h-3.5 mr-1.5" />
                        Approve Publication (Locked)
                      </Button>
                      <div className="absolute right-0 top-full mt-1 hidden group-hover:block z-30 w-64 p-2 bg-surface border border-line rounded-lg text-[11px] text-ink">
                        Standard approval is locked by {openBlockers.length} active blocker(s). Remediate blockers or execute an authorized override.
                      </div>
                    </div>

                    {/* Authorized Override Button for Brand Managers and Admins */}
                    {isBrandManagerOrAdmin && (
                      <Button
                        size="sm"
                        onClick={() => {
                          setIsOverrideMode(true);
                          setApprovalModalOpen(true);
                        }}
                        className="bg-amber-600 hover:bg-amber-500 text-white border-amber-500/40 text-xs font-semibold"
                      >
                        <Unlock className="w-3.5 h-3.5 mr-1.5" />
                        Override Blockers & Approve
                      </Button>
                    )}
                  </>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => {
                      setIsOverrideMode(false);
                      setApprovalModalOpen(true);
                    }}
                    className="bg-emerald-600 hover:bg-emerald-500 border-emerald-500/40 text-white text-xs font-semibold"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                    Approve Publication
                  </Button>
                )}
              </>
            ) : (
              <div className="text-xs text-ink-soft bg-surface border border-line px-3 py-1.5 rounded-lg flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5 text-accent-ink" />
                <span>Viewing as Creator (Read Only Approval)</span>
              </div>
            )}
          </div>
        </div>

        {/* GOVERNANCE PIPELINE TELEMETRY STEPPER */}
        {review && (
          <PipelineStepper
            review={review}
            onRetry={handleReEvaluate}
            isRetrying={reEvaluating}
          />
        )}

        {/* PROCESSING IN PROGRESS BANNER */}
        {(review?.processing_status === "Processing" ||
          review?.processing_status === "Extracting" ||
          review?.processing_status === "Submitting") && (
          <div className="p-4 rounded-xl bg-accent-soft/30 border border-accent/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-ink animate-in fade-in">
            <div className="flex items-start sm:items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center shrink-0">
                <RefreshCw className="w-4 h-4 text-accent-ink animate-spin" />
              </div>
              <div>
                <p className="font-semibold text-ink text-sm flex items-center gap-2">
                  <span>Brand Governance Scan In Progress</span>
                  <Badge variant="status" value="Processing" />
                </p>
                <p className="text-ink-soft text-xs mt-0.5">
                  BrandProof is actively analysing the submitted content and verifying claims against approved facts and brand guidelines (CitationGate). You can safely navigate away and return at any time.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchReview()}
                className="text-xs bg-paper border-line-strong hover:bg-sunken"
              >
                <RefreshCw className="w-3 h-3 mr-1.5" />
                Refresh Status
              </Button>
            </div>
          </div>
        )}

        {/* PROCESSING FAILED BANNER */}
        {review?.processing_status === "Failed" && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-600/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-rose-200 animate-in fade-in">
            <div className="flex items-start sm:items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shrink-0">
                <AlertOctagon className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <p className="font-semibold text-rose-100 text-sm">
                  Evaluation Analysis Failed
                </p>
                <p className="text-rose-300/90 text-xs mt-0.5">
                  {review.error_message || "An unexpected error occurred during document extraction or claim verification."}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              <Button
                size="sm"
                onClick={handleReEvaluate}
                isLoading={reEvaluating}
                className="bg-rose-600 hover:bg-rose-500 text-white border-transparent text-xs"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Retry Evaluation
              </Button>
            </div>
          </div>
        )}

        {/* CLAIMS & GOVERNANCE EVALUATION SUMMARY CARDS */}
        {review && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-ink-soft">
                <span>Total Claims</span>
                <Tag className="w-3.5 h-3.5 text-accent-ink" />
              </div>
              <div className="text-2xl font-bold text-ink mt-1">
                {claimCounts.total}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">Claims detected</p>
            </div>

            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-emerald-400">
                <span>Supported</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {claimCounts.supported}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">Verified facts</p>
            </div>

            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-rose-400">
                <span>Conflicting</span>
                <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
              </div>
              <div className="text-2xl font-bold text-rose-400 mt-1">
                {claimCounts.conflicts}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">Contradicts truth</p>
            </div>

            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-amber-400">
                <span>Unsupported</span>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <div className="text-2xl font-bold text-amber-400 mt-1">
                {claimCounts.unsupported}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">No source found</p>
            </div>

            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-orange-400">
                <span>Expired Scope</span>
                <Clock className="w-3.5 h-3.5 text-orange-400" />
              </div>
              <div className="text-2xl font-bold text-orange-400 mt-1">
                {claimCounts.expired}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">Past expiration</p>
            </div>

            <div className="p-3 rounded-xl bg-surface border border-line">
              <div className="flex items-center justify-between text-xs text-cyan-400">
                <span>Out of Scope</span>
                <Globe className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div className="text-2xl font-bold text-cyan-400 mt-1">
                {claimCounts.out_of_scope}
              </div>
              <p className="text-[11px] text-ink-mute mt-0.5">Wrong product/region</p>
            </div>
          </div>
        )}

        {/* PROMINENT BLOCKER POLICY ALERT BANNER */}
        {hasOpenBlockers && (
          <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-600/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-rose-200">
            <div className="flex items-start sm:items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shrink-0">
                <AlertOctagon className="w-5 h-5 text-rose-400 animate-pulse" />
              </div>
              <div>
                <p className="font-semibold text-rose-100 text-sm">
                  Active Blocker(s) Detected ({openBlockers.length}) — Publication Locked
                </p>
                <p className="text-rose-300/90 text-xs mt-0.5">
                  Brand governance policy prevents publication until all blocker findings are remediated.
                  Brand Managers or Admins may execute an authorized override with documented rationale.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setActiveTab("findings");
                  setFindingSeverityFilter("blocker");
                }}
                className="bg-rose-950/60 border-rose-800 hover:bg-rose-900 text-rose-200 text-xs"
              >
                Inspect Blockers ({openBlockers.length})
              </Button>
            </div>
          </div>
        )}

        {/* INTENT CARD CONTEXT SUMMARY */}
        {review && (
          <div className="p-4 rounded-lg bg-surface border border-line space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-line">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                <Compass className="w-4 h-4 text-accent-ink" />
                <span>Intent Card & Governed Target Scopes</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20">
                  Strict Source Traced
                </span>
                {docData && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownload}
                    isLoading={downloading}
                    className="text-xs h-7 px-2.5 text-ink border-line-strong hover:bg-sunken"
                  >
                    <Download className="w-3 h-3 mr-1" />
                    Download Original
                  </Button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Product</span>
                <span className="text-accent-ink font-medium truncate block mt-0.5">
                  {review.product || docData?.product || "All Products"}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Region</span>
                <span className="text-ink font-medium truncate block mt-0.5">
                  {review.region || docData?.region || "Global"}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Channel</span>
                <span className="text-ink font-medium truncate block mt-0.5">
                  {review.channel || docData?.channel || "All Channels"}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Content Type</span>
                <span className="text-ink font-medium truncate block mt-0.5">
                  {review.content_type || "Marketing Draft"}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Target Audience</span>
                <span className="text-ink font-medium truncate block mt-0.5">
                  {review.intended_audience || "Enterprise Customers"}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-mute block">Status</span>
                <span className="text-emerald-400 font-medium truncate block mt-0.5">
                  {docData?.processing_status || "Ready"}
                </span>
              </div>
            </div>

            {(review.purpose || (review.intent_card && review.intent_card.purpose)) && (
              <div className="p-2.5 rounded-lg bg-paper border border-line text-xs text-ink flex items-start gap-2">
                <span className="text-ink-mute font-semibold shrink-0">Strategic Intent:</span>
                <span>{review.purpose || review.intent_card?.purpose}</span>
              </div>
            )}
          </div>
        )}

        {/* DISTINCT WORKSPACE TABS */}
        <div className="border-b border-line flex items-center gap-1 overflow-x-auto text-sm">
          {/* Tab 0: Overview & Scorecard */}
          <button
            onClick={() => setActiveTab("overview")}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "overview"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <Layers className="w-4 h-4 text-accent-ink" />
            <span>Overview & Scorecard</span>
          </button>

          {/* Tab 1: Findings */}
          <button
            onClick={() => setActiveTab("findings")}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "findings"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Findings</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                findingCounts.blocker > 0
                  ? "bg-rose-500/20 text-rose-300 font-semibold"
                  : "bg-sunken text-ink"
              }`}
            >
              {findingCounts.total}
            </span>
          </button>

          {/* Tab 2: Claim Ledger */}
          <button
            onClick={() => setActiveTab("ledger")}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "ledger"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
            <span>Claim Ledger</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-sunken text-ink font-mono">
              {claimCounts.total}
            </span>
          </button>

          {/* Tab 3: Changes / Diff */}
          <button
            onClick={() => {
              setActiveTab("diff");
              fetchDiff();
            }}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "diff"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <FileDiff className="w-4 h-4 text-cyan-400" />
            <span>Changes / Diff</span>
            {diffData && diffData.stats.total_changes > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-accent-soft text-accent-ink font-mono">
                {diffData.stats.total_changes} edits
              </span>
            )}
          </button>

          {/* Tab 4: Activity & Comments */}
          <button
            onClick={() => setActiveTab("activity")}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "activity"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <MessageSquare className="w-4 h-4 text-purple-400" />
            <span>Activity & Comments</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-sunken text-ink font-mono">
              {comments.length + (review?.approvals?.length || 0)}
            </span>
          </button>

          {/* Tab 5: Evidence Documents */}
          <button
            onClick={() => setActiveTab("evidence")}
            className={`flex items-center gap-2 py-3 px-4 font-medium transition-all border-b-2 -mb-px shrink-0 ${
              activeTab === "evidence"
                ? "border-accent text-ink bg-sunken/60 rounded-t-lg"
                : "border-transparent text-ink-soft hover:text-ink hover:border-line-strong"
            }`}
          >
            <Paperclip className="w-4 h-4 text-blue-400" />
            <span>Evidence</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-sunken text-ink font-mono">
              {review?.evidence_documents?.length || 0}
            </span>
          </button>
        </div>

        {/* TAB 0: OVERVIEW & SCORECARD TAB */}
        {activeTab === "overview" && review && (
          <EvaluationScorecard
            review={review}
            onSelectTab={setActiveTab}
            onAcceptFix={handleAcceptFix}
            onFilterSeverity={setFindingSeverityFilter}
            acceptingFixId={acceptingFixId}
          />
        )}

        {/* TAB 1: FINDINGS TAB */}
        {activeTab === "findings" && (
          <div className="space-y-4">
            {/* Filter and stats row */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 rounded-lg bg-surface border border-line">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-soft flex items-center gap-1 mr-1">
                  <Filter className="w-3.5 h-3.5" /> Severity:
                </span>
                <button
                  type="button"
                  onClick={() => setFindingSeverityFilter("all")}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    findingSeverityFilter === "all"
                      ? "bg-accent border-accent text-ink"
                      : "bg-paper border-line text-ink-soft hover:text-ink"
                  }`}
                >
                  All ({findingCounts.total})
                </button>
                <button
                  type="button"
                  onClick={() => setFindingSeverityFilter("blocker")}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    findingSeverityFilter === "blocker"
                      ? "bg-rose-600 border-rose-500 text-white"
                      : "bg-paper border-line text-rose-400 hover:bg-rose-950/30"
                  }`}
                >
                  Blocker ({findingCounts.blocker})
                </button>
                <button
                  type="button"
                  onClick={() => setFindingSeverityFilter("high")}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    findingSeverityFilter === "high"
                      ? "bg-amber-600 border-amber-500 text-white"
                      : "bg-paper border-line text-amber-400 hover:bg-amber-950/30"
                  }`}
                >
                  High ({findingCounts.high})
                </button>
                <button
                  type="button"
                  onClick={() => setFindingSeverityFilter("warning")}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    findingSeverityFilter === "warning"
                      ? "bg-yellow-600 border-yellow-500 text-ink"
                      : "bg-paper border-line text-yellow-400 hover:bg-yellow-950/30"
                  }`}
                >
                  Warning ({findingCounts.warning})
                </button>
                <button
                  type="button"
                  onClick={() => setFindingSeverityFilter("info")}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    findingSeverityFilter === "info"
                      ? "bg-sky-600 border-sky-500 text-white"
                      : "bg-paper border-line text-sky-400 hover:bg-sky-950/30"
                  }`}
                >
                  Info ({findingCounts.info})
                </button>
              </div>

              {/* Status filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink-soft">Status:</span>
                <select
                  value={findingStatusFilter}
                  onChange={(e) => setFindingStatusFilter(e.target.value)}
                  className="bg-paper border border-line-strong rounded-lg px-2.5 py-1 text-xs text-ink focus:outline-none focus:border-accent"
                >
                  <option value="all">All Statuses</option>
                  <option value="open">Open Only</option>
                  <option value="resolved">Resolved / Fixed</option>
                  <option value="dismissed">Dismissed Only</option>
                </select>
              </div>
            </div>

            {/* Findings List */}
            {filteredFindings.length > 0 ? (
              <div className="space-y-4">
                {filteredFindings.map((finding, idx) => {
                  const isBlocker = finding.severity === "Blocker" || finding.severity === "Critical";
                  const isOpen = finding.status === "Open";
                  const isDismissed = finding.status === "Dismissed" || finding.status === "Waived";
                  const isFixed = finding.status === "Fixed" || finding.status === "Resolved";
                  const hasRemediation = Boolean(finding.suggestion || finding.suggested_replacement);

                  return (
                    <div
                      key={finding.id}
                      className={`p-4 rounded-lg border transition-all ${
                        isBlocker && isOpen
                          ? "bg-paper border-rose-500/50  ring-1 ring-rose-500/30"
                          : isFixed
                          ? "bg-paper border-line opacity-80"
                          : "bg-paper border-line hover:border-line-strong"
                      }`}
                    >
                      {/* Top finding meta */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-line">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-semibold text-ink-mute">
                            #{idx + 1}
                          </span>
                          <Badge variant="severity" value={finding.severity} />
                          <Badge variant="status" value={finding.status} />
                          {finding.checker && (
                            <span className="text-[11px] font-mono text-ink-soft bg-surface px-2 py-0.5 rounded border border-line">
                              {finding.checker}
                            </span>
                          )}
                        </div>

                        {/* Citation status */}
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-mono bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Citation Validated</span>
                        </div>
                      </div>

                      {/* Finding Title & Message */}
                      <div className="mt-3 space-y-2">
                        {finding.title && (
                          <h4 className="text-sm font-semibold text-ink">
                            {finding.title}
                          </h4>
                        )}
                        <p className="text-xs text-ink leading-relaxed">
                          {finding.message}
                        </p>

                        {/* Quoted draft text snippet */}
                        {finding.quoted_text && (
                          <div className="p-3 rounded-lg bg-surface border border-line space-y-1">
                            <span className="text-[11px] text-ink-mute font-semibold block">
                              Quoted Draft Excerpt:
                            </span>
                            <p className="text-xs font-mono text-rose-300 bg-rose-500/10 px-2 py-1 rounded border border-rose-500/20">
                              &ldquo;{finding.quoted_text}&rdquo;
                            </p>
                          </div>
                        )}

                        {/* Remediation / Suggestion Box */}
                        {hasRemediation && (
                          <div className="p-3 rounded-lg bg-accent-soft border border-accent/30 space-y-2">
                            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-accent-ink">
                              <span>Suggested fix</span>
                            </div>
                            <p className="text-xs text-accent-ink font-medium">
                              {finding.suggested_replacement || finding.suggestion}
                            </p>
                          </div>
                        )}

                        {/* Dismissal Reason Note if dismissed */}
                        {isDismissed && finding.dismissal_reason && (
                          <div className="p-2.5 rounded-lg bg-surface border border-line text-xs text-ink-soft flex items-start gap-2">
                            <Info className="w-4 h-4 text-ink-mute shrink-0 mt-0.5" />
                            <div>
                              <strong className="text-ink">Dismissal Justification:</strong>{" "}
                              {finding.dismissal_reason}
                            </div>
                          </div>
                        )}

                        {/* Fixed in v(N) Note */}
                        {isFixed && (
                          <div className="p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-900/50 text-xs text-emerald-300 flex items-center gap-2">
                            <CheckCheck className="w-4 h-4 text-emerald-400" />
                            <span>Remediated in revised document version.</span>
                          </div>
                        )}

                        {/* Source of Truth Attribution Badge */}
                        <div className="pt-2 flex flex-wrap items-center justify-between gap-2 text-xs border-t border-line">
                          <div className="flex items-center gap-2">
                            <span className="text-ink-mute text-[11px]">Approved Source:</span>
                            <span className="font-mono text-[11px] text-emerald-400 bg-emerald-950/30 px-2 py-0.5 rounded border border-emerald-900/40 truncate max-w-sm">
                              {finding.source_reference}
                            </span>
                          </div>

                          {/* Action Toolbar for Reviewer / Brand Manager */}
                          <div className="flex items-center gap-2">
                            {isOpen && (
                              <>
                                {hasRemediation && isReviewerOrAdmin && (
                                  <Button
                                    size="sm"
                                    onClick={() => handleAcceptFix(finding)}
                                    isLoading={acceptingFixId === finding.id}
                                    className="bg-accent hover:bg-accent-hover text-ink text-xs h-7 px-3"
                                  >
                                                    Accept Fix (Creates v{currentVersionNumber + 1})
                                  </Button>
                                )}

                                {isReviewerOrAdmin && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => openDismissModal(finding)}
                                    className="text-xs h-7 px-2.5 border-line-strong hover:bg-sunken text-ink"
                                  >
                                    Dismiss
                                  </Button>
                                )}
                              </>
                            )}

                            <button
                              type="button"
                              onClick={() => {
                                setNewCommentFindingId(finding.id);
                                setActiveTab("activity");
                              }}
                              className="text-xs text-ink-soft hover:text-accent-ink flex items-center gap-1 transition-colors px-2 py-1"
                            >
                              <MessageSquare className="w-3 h-3" />
                              <span>Comment</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12 rounded-lg bg-sunken/60 border border-line text-ink-soft space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
                <h3 className="text-base font-semibold text-ink">No findings</h3>
                <p className="text-xs text-ink-soft max-w-md mx-auto">
                  {findingSeverityFilter !== "all" || findingStatusFilter !== "all"
                    ? "No findings match the current filter criteria."
                    : "Every claim has a supporting source. This draft is ready for sign-off."}
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: CLAIM LEDGER TAB */}
        {activeTab === "ledger" && (
          <div className="space-y-4">
            {/* Claims Metric Summary Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3 rounded-lg bg-surface border border-line">
                <span className="text-[11px] text-ink-soft block">Total Claims</span>
                <span className="text-lg font-semibold text-ink font-mono mt-0.5 block">{claimCounts.total}</span>
              </div>
              <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-900/50">
                <span className="text-[11px] text-emerald-400 block">Supported</span>
                <span className="text-lg font-semibold text-emerald-400 font-mono mt-0.5 block">{claimCounts.supported}</span>
              </div>
              <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/50">
                <span className="text-[11px] text-rose-400 block">Conflicts</span>
                <span className="text-lg font-semibold text-rose-400 font-mono mt-0.5 block">{claimCounts.conflicts}</span>
              </div>
              <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-900/50">
                <span className="text-[11px] text-amber-400 block">Expired Fact</span>
                <span className="text-lg font-semibold text-amber-400 font-mono mt-0.5 block">{claimCounts.expired}</span>
              </div>
              <div className="p-3 rounded-lg bg-yellow-950/30 border border-yellow-900/50">
                <span className="text-[11px] text-yellow-400 block">Out of Scope</span>
                <span className="text-lg font-semibold text-yellow-400 font-mono mt-0.5 block">{claimCounts.out_of_scope}</span>
              </div>
              <div className="p-3 rounded-lg bg-paper border border-line">
                <span className="text-[11px] text-ink-soft block">Unsupported</span>
                <span className="text-lg font-semibold text-ink-soft font-mono mt-0.5 block">{claimCounts.unsupported}</span>
              </div>
            </div>

            {/* Filter buttons */}
            <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-surface border border-line">
              <span className="text-xs text-ink-soft flex items-center gap-1 mr-1">
                <Filter className="w-3.5 h-3.5" /> Ledger Status:
              </span>
              {(["all", "SUPPORTED", "CONFLICTS", "EXPIRED", "OUT_OF_SCOPE", "UNSUPPORTED"] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setClaimStatusFilter(st)}
                  className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                    claimStatusFilter === st
                      ? "bg-accent border-accent text-ink"
                      : "bg-paper border-line text-ink-soft hover:text-ink"
                  }`}
                >
                  {st === "all" ? "All Claims" : st}
                </button>
              ))}
            </div>

            {/* Claims Ledger Items */}
            {filteredClaims.length > 0 ? (
              <div className="space-y-3">
                {filteredClaims.map((claim, idx) => {
                  const isConflict = claim.status === "CONFLICTS" || claim.status === "Disputed";
                  const isExpired = claim.status === "EXPIRED";
                  const isSupported = claim.status === "SUPPORTED" || claim.status === "Verified";

                  return (
                    <div
                      key={claim.id}
                      className={`p-4 rounded-lg border transition-all ${
                        isConflict
                          ? "bg-paper border-rose-500/40"
                          : isExpired
                          ? "bg-paper border-amber-500/40"
                          : isSupported
                          ? "bg-paper border-emerald-500/30"
                          : "bg-paper border-line"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-line">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-semibold text-accent-ink">
                            Claim #{idx + 1}
                          </span>
                          {claim.claim_type && (
                            <span className="text-[11px] font-mono text-ink-soft bg-surface px-2 py-0.5 rounded border border-line">
                              {claim.claim_type}
                            </span>
                          )}
                          <span className="text-[11px] text-ink-mute font-mono">
                            Confidence: {Math.round((claim.confidence || 0.9) * 100)}%
                          </span>
                        </div>

                        {/* Status Badge */}
                        <span
                          className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border font-mono ${
                            isSupported
                              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                              : isConflict
                              ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                              : isExpired
                              ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                              : "bg-sunken text-ink-soft border-line-strong"
                          }`}
                        >
                          {claim.status}
                        </span>
                      </div>

                      <div className="mt-2.5 space-y-2">
                        {/* Claim Text */}
                        <p className="text-xs font-medium text-ink leading-relaxed bg-surface p-2.5 rounded-lg border border-line">
                          &ldquo;{claim.text || claim.claim_text}&rdquo;
                        </p>

                        {/* Reasoning & Source details */}
                        {claim.reasoning && (
                          <div className="text-xs text-ink flex items-start gap-2 bg-sunken/60 p-2 rounded">
                            <span className="text-ink-mute font-semibold shrink-0">Audit Reasoning:</span>
                            <span>{claim.reasoning}</span>
                          </div>
                        )}

                        {claim.matched_fact_id && (
                          <div className="flex items-center gap-2 text-[11px] text-ink-soft pt-1">
                            <span className="text-ink-mute">Matched Fact Citation:</span>
                            <span className="font-mono text-accent-ink bg-accent-soft px-2 py-0.5 rounded border border-accent/30">
                              {claim.matched_fact_title ? `${claim.matched_fact_title} (${claim.matched_fact_id.slice(0, 8)})` : `Fact ID: ${claim.matched_fact_id}`}
                            </span>
                          </div>
                        )}

                        {/* Linked Evidence Document or Link Action */}
                        <div className="pt-2 border-t border-line">
                          {claim.evidence_id ? (
                            <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs">
                              <div className="flex items-center gap-2 text-emerald-400">
                                <FileCheck2 className="w-4 h-4 shrink-0" />
                                <span className="font-medium text-[11px]">
                                  Backed by Evidence: <strong>{claim.evidence_title || `Evidence ID: ${claim.evidence_id.slice(0, 8)}`}</strong>
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleUnlinkClaimEvidence(claim.id)}
                                  className="h-6 text-[11px] px-2 text-ink-mute hover:text-rose-400 hover:bg-rose-500/10"
                                  title="Unlink evidence document"
                                >
                                  <Unlink className="w-3 h-3 mr-1" />
                                  Unlink Evidence
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg bg-surface border border-line text-xs">
                              <span className="text-ink-mute text-[11px] flex items-center gap-1.5">
                                <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                                CitationGate: No supporting corporate evidence document linked to this statement.
                              </span>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleOpenClaimLinkModal(claim)}
                                className="h-6 text-[11px] px-2.5 text-accent-ink border-accent/30 hover:bg-accent-soft"
                              >
                                <Paperclip className="w-3 h-3 mr-1" />
                                Link Evidence
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12 rounded-lg bg-sunken/60 border border-line text-ink-mute text-xs">
                No claims match the selected status filter.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: CHANGES / DIFF TAB */}
        {activeTab === "diff" && (
          <div className="space-y-4">
            {diffLoading ? (
              <div className="space-y-3 py-8">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-64 w-full" />
              </div>
            ) : diffData ? (
              <div className="space-y-4">
                {/* Diff Header Bar */}
                <div className="p-4 rounded-lg bg-surface border border-line flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <GitPullRequest className="w-4 h-4 text-accent-ink" />
                      <h3 className="text-sm font-semibold text-ink">
                        Comparing Version {diffData.base_version.version_number} → Version {diffData.current_version.version_number}
                      </h3>
                    </div>
                    {diffData.current_version.change_reason && (
                      <p className="text-xs text-accent-ink">
                        <strong>Change Rationale:</strong> {diffData.current_version.change_reason}
                      </p>
                    )}
                  </div>

                  {/* Summary Metric Chips */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      +{diffData.stats.words_added} words added
                    </span>
                    <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      -{diffData.stats.words_removed} words removed
                    </span>
                    <span className="text-xs font-mono text-ink-soft px-2 py-1 rounded-lg bg-paper border border-line">
                      {diffData.stats.words_unchanged} unchanged
                    </span>
                  </div>
                </div>

                {/* Diff Display Card */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between w-full">
                      <div>
                        <CardTitle>Word-Level Remediation Diff</CardTitle>
                        <CardDescription>
                          Fine-grained token revisions between ingested original and remediated draft
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-1.5 bg-paper border border-line rounded-lg p-0.5 text-xs">
                        <button
                          type="button"
                          onClick={() => setDiffViewMode("inline")}
                          className={`px-2.5 py-1 rounded font-medium transition-colors ${
                            diffViewMode === "inline"
                              ? "bg-accent text-ink"
                              : "text-ink-soft hover:text-ink"
                          }`}
                        >
                          Inline Word Diff
                        </button>
                      </div>
                    </div>
                  </CardHeader>

                  <div className="p-4 rounded-lg bg-paper border border-line font-mono text-xs leading-relaxed max-h-[550px] overflow-y-auto whitespace-pre-wrap">
                    {diffData.tokens.map((token, i) => {
                      if (token.type === "added") {
                        return (
                          <span
                            key={i}
                            className="bg-emerald-500/20 text-emerald-300 font-semibold px-1 py-0.5 rounded border border-emerald-500/40 inline-block mr-1"
                          >
                            {token.value}
                          </span>
                        );
                      }
                      if (token.type === "removed") {
                        return (
                          <span
                            key={i}
                            className="bg-rose-500/20 text-rose-300 line-through px-1 py-0.5 rounded border border-rose-500/40 inline-block mr-1"
                          >
                            {token.value}
                          </span>
                        );
                      }
                      return <span key={i} className="text-ink">{token.value} </span>;
                    })}
                  </div>
                </Card>
              </div>
            ) : (
              <div className="text-center py-12 rounded-lg bg-sunken/60 border border-line text-ink-soft space-y-3">
                <FileCode className="w-10 h-10 text-accent-ink mx-auto" />
                <h3 className="text-base font-semibold text-ink">Version 1.0 — Initial Ingestion</h3>
                <p className="text-xs text-ink-soft max-w-md mx-auto">
                  This document is currently on its initial version. When you remediate or accept a suggested fix on any finding in the Findings tab, BrandProof automatically produces Version 2 and generates an interactive word-by-word diff here.
                </p>
                <div className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setActiveTab("findings")}
                    className="text-xs text-accent-ink border-accent/40 hover:bg-accent-soft"
                  >
                    Go to Findings to Accept a Fix
                  </Button>
                </div>
              </div>
            )}

            {/* Document decomposed chunks / raw view */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between w-full">
                  <div>
                    <CardTitle>Ingested Document Breakdown</CardTitle>
                    <CardDescription>
                      {chunks.length} decomposed semantic chunks from {docData?.filename}
                    </CardDescription>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopyRaw(currentExtractedText)}
                    className="p-1.5 rounded bg-surface hover:bg-sunken text-ink-soft hover:text-ink text-xs flex items-center gap-1 border border-line"
                  >
                    {copiedText ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-[11px] text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span className="text-[11px]">Copy Text</span>
                      </>
                    )}
                  </button>
                </div>
              </CardHeader>

              <div className="space-y-2.5 max-h-[400px] overflow-y-auto pr-1">
                {chunks.map((ch) => (
                  <div
                    key={ch.id}
                    className="p-3 rounded-lg bg-paper border border-line space-y-1"
                  >
                    <div className="flex items-center justify-between text-[11px] text-ink-mute">
                      <span className="font-mono text-accent-ink font-semibold">
                        #{ch.sequence} • {ch.chunk_type.toUpperCase()}
                      </span>
                      {ch.page_number && <span>Page {ch.page_number}</span>}
                    </div>
                    <p className="text-xs text-ink leading-relaxed font-normal">
                      {ch.text}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* TAB 4: ACTIVITY & COMMENTS TAB */}
        {activeTab === "activity" && (
          <div className="space-y-6">
            {/* Post new comment form */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Add Reviewer Comment or Clarification</CardTitle>
                </div>
              </CardHeader>
              <form onSubmit={handleAddComment} className="space-y-3">
                {review?.findings && review.findings.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-ink-soft shrink-0">Link to Finding (optional):</span>
                    <select
                      value={newCommentFindingId}
                      onChange={(e) => setNewCommentFindingId(e.target.value)}
                      className="bg-paper border border-line-strong rounded-lg px-2.5 py-1 text-xs text-ink focus:outline-none focus:border-accent w-full max-w-md"
                    >
                      <option value="">General Review Comment</option>
                      {review.findings.map((f, i) => (
                        <option key={f.id} value={f.id}>
                          Finding #{i + 1} ({f.severity}: {f.title || f.message.substring(0, 40)}...)
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <textarea
                  rows={3}
                  value={newCommentText}
                  onChange={(e) => setNewCommentText(e.target.value)}
                  placeholder="Leave governance guidance, feedback for the creator, or compliance context..."
                  className="w-full bg-paper border border-line-strong rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-accent"
                />

                <div className="flex justify-end">
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!newCommentText.trim()}
                    isLoading={submittingComment}
                    className="bg-accent hover:bg-accent-hover text-ink text-xs"
                  >
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    Post Comment
                  </Button>
                </div>
              </form>
            </Card>

            {/* Combined Timeline of Human Approvals, Comments, and Milestones */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
                <Clock className="w-4 h-4 text-accent-ink" />
                <span>Governance Audit Trail & Discussions</span>
              </h3>

              {/* Approvals */}
              {review?.approvals && review.approvals.length > 0 && (
                <div className="space-y-3">
                  {review.approvals.map((appr) => (
                    <div
                      key={appr.id}
                      className={`p-4 rounded-lg border ${
                        appr.is_override
                          ? "bg-amber-950/20 border-amber-500/40"
                          : appr.status === "Approved"
                          ? "bg-emerald-950/20 border-emerald-500/40"
                          : "bg-paper border-line"
                      }`}
                    >
                      <div className="flex items-center justify-between pb-2 border-b border-line">
                        <div className="flex items-center gap-2">
                          <UserCheck className="w-4 h-4 text-accent-ink" />
                          <span className="text-xs font-semibold text-ink">
                            {appr.approver_name || "Authorized Reviewer"}
                          </span>
                          <Badge variant="status" value={appr.status} />
                          {appr.is_override && (
                            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold">
                              BLOCKER OVERRIDE
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-ink-mute font-mono">
                          {formatDate(appr.decided_at)}
                        </span>
                      </div>

                      <div className="mt-2 text-xs space-y-1.5">
                        {appr.comments && (
                          <p className="text-ink italic">
                            &ldquo;{appr.comments}&rdquo;
                          </p>
                        )}
                        {appr.is_override && appr.override_reason && (
                          <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-900/60 text-amber-200">
                            <strong>Compliance Override Rationale:</strong> {appr.override_reason}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Comments */}
              {comments.length > 0 ? (
                <div className="space-y-3">
                  {comments.map((comm) => (
                    <div
                      key={comm.id}
                      className="p-3.5 rounded-lg bg-paper border border-line space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-accent-soft text-accent-ink font-semibold text-[11px] flex items-center justify-center">
                            {comm.author_name ? comm.author_name[0].toUpperCase() : "U"}
                          </div>
                          <span className="text-xs font-semibold text-ink">
                            {comm.author_name || "Reviewer"}
                          </span>
                          {comm.finding_id && (
                            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20">
                              Linked to Finding
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-ink-mute">
                          {formatRelativeTime(comm.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-ink whitespace-pre-wrap leading-relaxed pl-8">
                        {comm.text}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-ink-mute text-xs">
                  No comments yet. Start the conversation above!
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: EVIDENCE DOCUMENTS TAB */}
        {activeTab === "evidence" && (
          <div className="space-y-4">
            {/* CitationGate Evidence Policy Card */}
            <div className="p-4 rounded-lg bg-surface border border-line flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center shrink-0">
                  <Shield className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <p className="font-semibold text-ink text-sm flex items-center gap-2">
                    <span>Supporting Corporate Evidence</span>
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20">
                      CitationGate Verified
                    </span>
                  </p>
                  <p className="text-ink-soft text-xs mt-0.5">
                    CitationGate enforces &quot;No valid source = no finding&quot;. Only Validated, non-expired evidence documents scoped to this review&apos;s product and region are accepted as factual justification.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleOpenAttachModal}
                  className="border-line-strong hover:bg-sunken text-xs text-ink"
                >
                  <Plus className="w-3.5 h-3.5 mr-1.5" />
                  Attach Existing Evidence
                </Button>

                <Link href="/evidence">
                  <Button
                    size="sm"
                    className="bg-accent hover:bg-accent-hover text-ink text-xs font-medium"
                  >
                    <Upload className="w-3.5 h-3.5 mr-1.5" />
                    Evidence Manager
                  </Button>
                </Link>
              </div>
            </div>

            {/* Evidence List */}
            {review?.evidence_documents && review.evidence_documents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {review.evidence_documents.map((doc: any) => {
                  const statusBadge = getEvidenceStatusBadge(doc.status, doc.is_expired);
                  return (
                    <Card key={doc.id} className="p-4 bg-surface border-line space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-2.5">
                          <div className="p-2 rounded bg-paper border border-line text-accent-ink shrink-0">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div className="space-y-0.5">
                            <h4 className="text-xs font-semibold text-ink line-clamp-1">{doc.title}</h4>
                            <p className="text-[11px] font-mono text-ink-mute truncate max-w-[220px]">
                              {doc.filename}
                            </p>
                          </div>
                        </div>

                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${statusBadge.colorClass}`}
                        >
                          {statusBadge.icon === "check" && <CheckCircle2 className="w-2.5 h-2.5" />}
                          {statusBadge.icon === "alert" && <AlertTriangle className="w-2.5 h-2.5" />}
                          {statusBadge.icon === "x" && <XCircle className="w-2.5 h-2.5" />}
                          <span>{statusBadge.label}</span>
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] bg-paper p-2.5 rounded-lg border border-line">
                        <div>
                          <span className="text-ink-mute block">File Size</span>
                          <span className="text-ink font-medium mt-0.5 block">{formatBytes(doc.file_size || 0)}</span>
                        </div>
                        <div>
                          <span className="text-ink-mute block">Product Scope</span>
                          <span className="text-accent-ink font-medium mt-0.5 block truncate">
                            {doc.product_scope || "All Products"}
                          </span>
                        </div>
                        <div>
                          <span className="text-ink-mute block">Uploaded</span>
                          <span className="text-ink font-medium mt-0.5 block">
                            {formatRelativeTime(doc.created_at)}
                          </span>
                        </div>
                        <div>
                          <span className="text-ink-mute block">Validity</span>
                          <span
                            className={`font-medium mt-0.5 block ${
                              doc.is_expired ? "text-rose-400 font-semibold" : "text-emerald-400"
                            }`}
                          >
                            {doc.is_expired
                              ? "Expired"
                              : doc.expires_at
                              ? `Expires ${formatDate(doc.expires_at)}`
                              : "Permanent"}
                          </span>
                        </div>
                      </div>

                      {doc.source_reference && (
                        <p className="text-[11px] text-ink-soft bg-paper p-2 rounded border border-line">
                          <span className="text-ink-mute font-semibold">Ref:</span> {doc.source_reference}
                        </p>
                      )}

                      <div className="flex items-center justify-between pt-1 border-t border-line text-xs">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => api.evidence.download(doc.id, doc.filename)}
                          className="h-7 text-[11px] px-2.5 border-line-strong hover:bg-sunken text-ink"
                        >
                          <Download className="w-3 h-3 mr-1" />
                          Download
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUnlinkEvidence(doc.id)}
                          className="h-7 text-[11px] px-2 text-ink-mute hover:text-rose-400 hover:bg-rose-500/10"
                        >
                          <Unlink className="w-3 h-3 mr-1" />
                          Unlink
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 text-center rounded-lg border border-dashed border-line-strong bg-surface space-y-3">
                <div className="w-10 h-10 rounded-full bg-paper border border-line flex items-center justify-center mx-auto text-ink-mute">
                  <Paperclip className="w-5 h-5" />
                </div>
                <div className="space-y-1 max-w-md mx-auto">
                  <h4 className="text-sm font-semibold text-ink">No Evidence Documents Attached</h4>
                  <p className="text-xs text-ink-soft">
                    This evaluation currently has no supporting documents attached. To substantiate claims that require independent verification, attach an existing document or upload a new one.
                  </p>
                </div>
                <div className="flex items-center justify-center gap-2 pt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleOpenAttachModal}
                    className="border-line-strong hover:bg-sunken text-xs text-ink"
                  >
                    <Plus className="w-3.5 h-3.5 mr-1.5" />
                    Attach Existing Evidence
                  </Button>
                  <Link href="/evidence">
                    <Button size="sm" className="bg-accent hover:bg-accent-hover text-ink text-xs font-medium">
                      <Upload className="w-3.5 h-3.5 mr-1.5" />
                      Upload New Evidence
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </div>
        )}

        {/* MODAL 1: HUMAN APPROVAL / BLOCKER OVERRIDE MODAL */}
        {approvalModalOpen && (
          <div className="fixed inset-0 z-50 bg-ink/30 flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-lg w-full p-6 shadow-soft space-y-4">
              <div className="flex items-center gap-2.5">
                {isOverrideMode ? (
                  <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                    <Unlock className="w-4 h-4" />
                  </div>
                ) : (
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                )}
                <div>
                  <h3 className="text-base font-semibold text-ink">
                    {isOverrideMode ? "Override Blockers & Approve Publication" : "Approve Content for Publication"}
                  </h3>
                </div>
              </div>

              {isOverrideMode && (
                <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-600/50 text-xs text-amber-200 space-y-1">
                  <p className="font-semibold text-amber-100 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    Authorized Executive Blocker Override
                  </p>
                  <p className="text-amber-300/90 text-[11px]">
                    This review contains {openBlockers.length} active blocker finding(s). By overriding, you certify under your Brand Manager / Admin authority that this content is authorized for release.
                  </p>
                </div>
              )}

              {isOverrideMode && (
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-amber-300">
                    Mandatory Business Justification (Min 10 characters) *
                  </label>
                  <textarea
                    rows={3}
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="Provide specific legal, executive, or business justification for overriding the blockers..."
                    className="w-full bg-paper border border-amber-500/40 rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-amber-400"
                  />
                  <span className="text-[11px] text-ink-mute">
                    {overrideReason.length}/10 characters minimum
                  </span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-ink">
                  Reviewer Notes & Decision Rationale
                </label>
                <textarea
                  rows={3}
                  value={approvalComments}
                  onChange={(e) => setApprovalComments(e.target.value)}
                  placeholder="Add any general guidance or notes for distribution teams..."
                  className="w-full bg-paper border border-line-strong rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-accent"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setApprovalModalOpen(false)}
                  disabled={submittingApproval}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleConfirmApproval}
                  isLoading={submittingApproval}
                  disabled={isOverrideMode && overrideReason.trim().length < 10}
                  className={
                    isOverrideMode
                      ? "bg-amber-600 hover:bg-amber-500 text-white font-semibold"
                      : "bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                  }
                >
                  {isOverrideMode ? "Confirm Blocker Override" : "Confirm Approval"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL 2: REQUEST CHANGES MODAL */}
        {changesModalOpen && (
          <div className="fixed inset-0 z-50 bg-ink/30 flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-lg w-full p-6 shadow-soft space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-ink">
                    Request Content Changes
                  </h3>
                  <p className="text-xs text-ink-soft">
                    Draft will be returned to the author with required revisions.
                  </p>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  Revision Instructions for Creator *
                </label>
                <textarea
                  rows={4}
                  value={changesComments}
                  onChange={(e) => setChangesComments(e.target.value)}
                  placeholder="Detail the exact claims, facts, or brand guidelines that must be updated before re-submission..."
                  className="w-full bg-paper border border-line-strong rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-accent"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setChangesModalOpen(false)}
                  disabled={submittingChanges}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleConfirmChanges}
                  isLoading={submittingChanges}
                  disabled={!changesComments.trim()}
                  className="bg-amber-600 hover:bg-amber-500 text-white font-semibold"
                >
                  Return to Author with Changes
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL 3: DISMISS FINDING MODAL */}
        {dismissModalOpen && dismissFinding && (
          <div className="fixed inset-0 z-50 bg-ink/30 flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-md w-full p-6 shadow-soft space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-sunken border border-line-strong flex items-center justify-center text-ink">
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-ink">
                    Dismiss Finding
                  </h3>
                  <p className="text-xs text-ink-soft">
                    Severity: <strong className="text-amber-400">{dismissFinding.severity}</strong>
                  </p>
                </div>
              </div>

              <p className="text-xs text-ink bg-paper p-2.5 rounded border border-line">
                {dismissFinding.title || dismissFinding.message}
              </p>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  Mandatory Business Justification *
                </label>
                <textarea
                  rows={3}
                  value={dismissReason}
                  onChange={(e) => setDismissReason(e.target.value)}
                  placeholder="State why this finding is dismissed (e.g. Legal 1-time exemption, out of scope channel, verified offline)..."
                  className="w-full bg-paper border border-line-strong rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-accent"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDismissModalOpen(false)}
                  disabled={dismissing}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleConfirmDismiss}
                  isLoading={dismissing}
                  disabled={!dismissReason.trim()}
                  className="bg-accent hover:bg-accent-hover text-ink font-semibold"
                >
                  Confirm Dismissal
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL 4: ATTACH EVIDENCE MODAL */}
        {attachEvidenceModalOpen && (
          <div className="fixed inset-0 z-50 bg-ink/30 flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-md w-full p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <div className="flex items-center gap-2">
                  <Paperclip className="w-4 h-4 text-accent-ink" />
                  <h3 className="text-base font-semibold text-ink">Attach Corporate Evidence</h3>
                </div>
                <button
                  onClick={() => setAttachEvidenceModalOpen(false)}
                  className="rounded-lg p-1 text-ink-mute hover:text-ink hover:bg-sunken"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleAttachEvidence} className="space-y-4 text-xs">
                <p className="text-ink-soft">
                  Select a corporate document from your organization&apos;s library to attach to this evaluation.
                </p>

                {availableEvidence.length === 0 ? (
                  <div className="p-4 rounded-lg bg-paper border border-line text-center space-y-2">
                    <p className="text-ink-mute">No unlinked evidence documents available.</p>
                    <Link href="/evidence">
                      <Button size="sm" className="bg-accent hover:bg-accent-hover text-ink text-xs">
                        <Upload className="w-3.5 h-3.5 mr-1" />
                        Go to Evidence Manager to Upload
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div>
                    <label className="block font-medium text-ink mb-1.5">Evidence Document</label>
                    <select
                      value={selectedAttachEvidenceId}
                      onChange={(e) => setSelectedAttachEvidenceId(e.target.value)}
                      required
                      className="w-full px-2.5 py-2 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="">Select an evidence document...</option>
                      {availableEvidence.map((ev) => (
                        <option key={ev.id} value={ev.id}>
                          {ev.title} ({ev.filename} • {ev.status})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setAttachEvidenceModalOpen(false)}
                    className="border-line-strong hover:bg-sunken text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    isLoading={linkingEvidence}
                    disabled={availableEvidence.length === 0 || !selectedAttachEvidenceId}
                    className="bg-accent hover:bg-accent-hover text-ink text-xs font-semibold"
                  >
                    Attach Document
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 5: LINK EVIDENCE TO CLAIM MODAL */}
        {claimLinkModalOpen && targetClaim && (
          <div className="fixed inset-0 z-50 bg-ink/30 flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-lg w-full p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <div className="flex items-center gap-2">
                  <FileCheck2 className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-base font-semibold text-ink">Link Evidence to Claim</h3>
                </div>
                <button
                  onClick={() => {
                    setClaimLinkModalOpen(false);
                    setTargetClaim(null);
                  }}
                  className="rounded-lg p-1 text-ink-mute hover:text-ink hover:bg-sunken"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleConfirmClaimLink} className="space-y-4 text-xs">
                {/* Quoted Claim Statement */}
                <div className="p-3 rounded-lg bg-paper border border-line space-y-1">
                  <span className="text-[11px] font-semibold text-ink-mute block">Claim Statement:</span>
                  <p className="text-xs text-ink font-medium">
                    &ldquo;{targetClaim.claim_text || targetClaim.text}&rdquo;
                  </p>
                </div>

                {availableEvidence.length === 0 ? (
                  <div className="p-4 rounded-lg bg-paper border border-line text-center space-y-2">
                    <p className="text-ink-mute">No corporate evidence documents available in your organization.</p>
                    <Link href="/evidence">
                      <Button size="sm" className="bg-accent hover:bg-accent-hover text-ink text-xs">
                        <Upload className="w-3.5 h-3.5 mr-1" />
                        Go to Evidence Manager to Upload
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <label className="block font-semibold text-ink mb-1.5">
                        Select Supporting Evidence Document *
                      </label>
                      <select
                        value={selectedClaimEvidenceId}
                        onChange={(e) => setSelectedClaimEvidenceId(e.target.value)}
                        required
                        className="w-full px-2.5 py-2 bg-paper border border-line-strong rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                      >
                        <option value="">Choose an evidence document...</option>
                        {availableEvidence.map((ev) => (
                          <option key={ev.id} value={ev.id}>
                            {ev.title} ({ev.filename} • {ev.effective_status || ev.status})
                          </option>
                        ))}
                      </select>
                      <p className="text-[11px] text-ink-mute mt-1">
                        Linking a Validated evidence document satisfies CitationGate and marks this claim statement as SUPPORTED.
                      </p>
                    </div>

                    <div>
                      <label className="block font-semibold text-ink mb-1.5">
                        Citation & Audit Rationale (Optional)
                      </label>
                      <input
                        type="text"
                        value={claimLinkReasoning}
                        onChange={(e) => setClaimLinkReasoning(e.target.value)}
                        placeholder="e.g. Page 14, Section 3.2 'Third-Party Compliance Attestation'"
                        className="w-full px-2.5 py-2 bg-paper border border-line-strong rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setClaimLinkModalOpen(false);
                      setTargetClaim(null);
                    }}
                    className="border-line-strong hover:bg-sunken text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    isLoading={linkingClaimEvidence}
                    disabled={availableEvidence.length === 0 || !selectedClaimEvidenceId}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                    Verify Claim with Evidence
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
