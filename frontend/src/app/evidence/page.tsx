"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  Plus,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Download,
  Trash2,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  FileCheck,
  FileSpreadsheet,
  Link as LinkIcon,
  Unlink,
  Eye,
  RefreshCw,
  X,
  Copy,
  Check,
  Calendar,
  Layers,
  Globe,
  Tag,
  Hash,
  AlertCircle,
  FileCode,
  Image as ImageIcon,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { Evidence, EvidenceDetail, EvidenceStatus, Review } from "@/lib/types";
import { formatDate, formatRelativeTime, formatBytes, getEvidenceStatusBadge } from "@/lib/utils";

export default function EvidencePage() {
  const { user } = useAuth();
  const { success, error, warning, info } = useToast();

  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [productFilter, setProductFilter] = useState<string>("All");

  // Reviews for association dropdowns
  const [availableReviews, setAvailableReviews] = useState<Review[]>([]);

  // Selected Evidence for Drawer/Modal
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [copiedChecksum, setCopiedChecksum] = useState(false);

  // Upload Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadSourceRef, setUploadSourceRef] = useState("");
  const [uploadProduct, setUploadProduct] = useState("All");
  const [uploadRegion, setUploadRegion] = useState("Global");
  const [uploadChannel, setUploadChannel] = useState("All");
  const [uploadExpiresAt, setUploadExpiresAt] = useState("");
  const [uploadReviewId, setUploadReviewId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  // Associate Modal State
  const [associateModalOpen, setAssociateModalOpen] = useState(false);
  const [targetEvidenceId, setTargetEvidenceId] = useState<string | null>(null);
  const [selectedReviewId, setSelectedReviewId] = useState("");
  const [associating, setAssociating] = useState(false);

  // Downloading State
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Fetch Evidence List
  const fetchEvidence = async () => {
    setLoading(true);
    try {
      const res = await api.evidence.list({
        status: statusFilter === "All" ? undefined : (statusFilter as EvidenceStatus),
        product: productFilter === "All" ? undefined : productFilter,
        q: search.trim() || undefined,
      });
      setEvidenceList(res);
    } catch (err: any) {
      error("Failed to load evidence", err.message || "Could not retrieve evidence records");
    } finally {
      setLoading(false);
    }
  };

  // Fetch available reviews for association selector
  const fetchReviewsList = async () => {
    try {
      const res = await api.reviews.list();
      setAvailableReviews(res);
    } catch (err) {
      console.warn("Could not load reviews for association", err);
    }
  };

  useEffect(() => {
    fetchEvidence();
    fetchReviewsList();
  }, [statusFilter, productFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchEvidence();
  };

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter("All");
    setProductFilter("All");
  };

  // Open Detailed Drawer
  const handleOpenDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const detail = await api.evidence.get(id);
      setSelectedEvidence(detail);
    } catch (err: any) {
      error("Error Loading Details", err.message || "Failed to load evidence details");
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle File Download
  const handleDownload = async (id: string, filename: string) => {
    setDownloadingId(id);
    try {
      await api.evidence.download(id, filename);
      success("Download Started", `Downloaded ${filename}`);
    } catch (err: any) {
      error("Download Failed", err.message || "Could not download evidence file");
    } finally {
      setDownloadingId(null);
    }
  };

  // Handle File Selection with Client Validation
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 15 MB limit
    if (file.size > 15 * 1024 * 1024) {
      error("File Too Large", "Evidence documents must be under 15 MB.");
      e.target.value = "";
      return;
    }

    const allowedExtensions = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      error("Unsupported Format", `Supported formats: PDF, DOCX, TXT, PNG, JPG/JPEG. Got: ${ext}`);
      e.target.value = "";
      return;
    }

    setUploadFile(file);
    if (!uploadTitle.trim()) {
      // Auto-populate title from clean filename
      const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
      setUploadTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }
  };

  // Handle Evidence Upload Submit
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      error("File Required", "Please choose an evidence file to upload.");
      return;
    }
    if (!uploadTitle.trim()) {
      error("Title Required", "Please provide a descriptive title for this evidence.");
      return;
    }

    setUploading(true);
    setUploadProgress(25);

    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("title", uploadTitle.trim());
      if (uploadDescription.trim()) formData.append("description", uploadDescription.trim());
      if (uploadSourceRef.trim()) formData.append("source_reference", uploadSourceRef.trim());
      if (uploadProduct.trim()) formData.append("product_scope", uploadProduct.trim());
      if (uploadRegion.trim()) formData.append("region_scope", uploadRegion.trim());
      if (uploadChannel.trim()) formData.append("channel_scope", uploadChannel.trim());
      if (uploadExpiresAt.trim()) formData.append("expires_at", uploadExpiresAt.trim());
      if (uploadReviewId.trim()) formData.append("review_id", uploadReviewId.trim());

      setUploadProgress(65);
      const created = await api.evidence.upload(formData);
      setUploadProgress(100);

      success(
        "Evidence Uploaded & Validated",
        `"${created.title}" is registered with status: ${created.status}.`
      );

      // Reset form
      setUploadModalOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadDescription("");
      setUploadSourceRef("");
      setUploadProduct("All");
      setUploadRegion("Global");
      setUploadChannel("All");
      setUploadExpiresAt("");
      setUploadReviewId("");
      fetchEvidence();
    } catch (err: any) {
      error("Upload Failed", err.message || "Failed to upload and validate evidence file.");
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  };

  // Handle Associate Evaluation Submit
  const handleAssociateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetEvidenceId || !selectedReviewId) {
      error("Selection Required", "Please select an evaluation to associate.");
      return;
    }

    setAssociating(true);
    try {
      await api.evidence.associate(targetEvidenceId, selectedReviewId);
      success("Evaluation Associated", "Evidence is now linked to the evaluation for CitationGate checks.");
      setAssociateModalOpen(false);
      setSelectedReviewId("");
      if (selectedEvidence && selectedEvidence.id === targetEvidenceId) {
        handleOpenDetail(targetEvidenceId);
      }
      fetchEvidence();
    } catch (err: any) {
      error("Association Failed", err.message || "Could not link evidence to evaluation.");
    } finally {
      setAssociating(false);
    }
  };

  // Handle Remove Association
  const handleRemoveAssociation = async (evidenceId: string, reviewId: string) => {
    if (!confirm("Are you sure you want to unlink this evidence from the evaluation?")) return;
    try {
      await api.evidence.removeAssociation(evidenceId, reviewId);
      success("Association Removed", "Evidence unlinked from evaluation.");
      if (selectedEvidence && selectedEvidence.id === evidenceId) {
        handleOpenDetail(evidenceId);
      }
      fetchEvidence();
    } catch (err: any) {
      error("Failed to Remove Link", err.message || "Could not unlink evidence.");
    }
  };

  // Handle Delete Evidence
  const handleDeleteEvidence = async (id: string, title: string) => {
    if (
      !confirm(
        `Are you sure you want to permanently delete "${title}"? This will safely remove the underlying storage object and all association records.`
      )
    ) {
      return;
    }

    try {
      await api.evidence.delete(id);
      success("Evidence Deleted", `"${title}" has been permanently removed.`);
      if (selectedEvidence && selectedEvidence.id === id) {
        setSelectedEvidence(null);
      }
      fetchEvidence();
    } catch (err: any) {
      error("Delete Failed", err.message || "Could not delete evidence file.");
    }
  };

  // Helper for File Icon
  const getFileIcon = (mime: string, ext?: string) => {
    if (mime.includes("pdf") || ext === "pdf") {
      return <FileText className="w-5 h-5 text-rose-400" />;
    }
    if (mime.includes("word") || ext === "docx") {
      return <FileCode className="w-5 h-5 text-blue-400" />;
    }
    if (mime.includes("image") || ["png", "jpg", "jpeg"].includes(ext || "")) {
      return <ImageIcon className="w-5 h-5 text-purple-400" />;
    }
    return <FileText className="w-5 h-5 text-slate-400" />;
  };

  // Summary Metrics
  const totalCount = evidenceList.length;
  const validatedCount = evidenceList.filter((e) => e.status === "Validated" && !e.is_expired).length;
  const expiredCount = evidenceList.filter((e) => e.is_expired || e.status === "Expired").length;
  const linkedCount = evidenceList.filter((e) => (e.associated_review_ids?.length || 0) > 0).length;

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl font-semibold tracking-tight text-ink">
              Evidence Management
            </h1>
            <p className="text-xs text-ink-soft mt-1">
              Upload, validate, and associate corporate evidence documents for strict CitationGate claim verification.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchEvidence}
              className="border-line-strong hover:bg-sunken text-xs h-9"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Refresh
            </Button>

            <Button
              size="sm"
              onClick={() => setUploadModalOpen(true)}
              className="bg-accent hover:bg-accent-hover text-ink text-xs font-medium h-9"
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" />
              Upload Evidence
            </Button>
          </div>
        </div>

        {/* CITATIONGATE GOVERNANCE POLICY BANNER */}
        <div className="p-4 rounded-lg bg-surface border border-line flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center shrink-0">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-ink flex items-center gap-2">
                <span>CitationGate Verification Invariant:</span>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20">
                  No Valid Source = No Finding
                </span>
              </p>
              <p className="text-xs text-ink-soft mt-0.5">
                Every factual marketing claim must be backed by a Validated, in-scope, non-expired evidence document or verified approved fact. Invalid magic bytes, expired dates, or cross-organization files are strictly quarantined.
              </p>
            </div>
          </div>
        </div>

        {/* Summary Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-surface border border-line">
            <span className="text-xs text-ink-mute block">Total Evidence</span>
            <span className="text-2xl font-semibold text-ink mt-1 block">{totalCount}</span>
            <span className="text-[11px] text-ink-soft mt-0.5 block">Stored corporate documents</span>
          </div>

          <div className="p-4 rounded-lg bg-surface border border-line">
            <span className="text-xs text-ink-mute block">Validated & Active</span>
            <span className="text-2xl font-semibold text-emerald-400 mt-1 block">{validatedCount}</span>
            <span className="text-[11px] text-emerald-400/80 mt-0.5 block">Ready for CitationGate</span>
          </div>

          <div className="p-4 rounded-lg bg-surface border border-line">
            <span className="text-xs text-ink-mute block">Expired / Quarantined</span>
            <span className={`text-2xl font-semibold mt-1 block ${expiredCount > 0 ? "text-rose-400" : "text-ink"}`}>
              {expiredCount}
            </span>
            <span className="text-[11px] text-ink-soft mt-0.5 block">Requires re-certification</span>
          </div>

          <div className="p-4 rounded-lg bg-surface border border-line">
            <span className="text-xs text-ink-mute block">Linked to Reviews</span>
            <span className="text-2xl font-semibold text-accent-ink mt-1 block">{linkedCount}</span>
            <span className="text-[11px] text-ink-soft mt-0.5 block">Supporting marketing drafts</span>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="p-3 rounded-lg bg-surface border border-line flex flex-col md:flex-row md:items-center justify-between gap-3">
          <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-ink-mute absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search by title, original filename, or scope..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-paper border border-line rounded-md text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
              />
            </div>
            <Button type="submit" size="sm" variant="outline" className="text-xs h-8 border-line-strong hover:bg-sunken">
              Search
            </Button>
          </form>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-ink-soft">
              <Filter className="w-3.5 h-3.5" />
              <span>Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by validation status"
                className="bg-paper border border-line rounded px-2 py-1 text-xs text-ink focus:outline-none focus:border-accent"
              >
                <option value="All">All Statuses</option>
                <option value="Validated">Validated</option>
                <option value="Processing">Processing</option>
                <option value="Uploaded">Uploaded</option>
                <option value="Expired">Expired</option>
                <option value="Invalid">Invalid Format</option>
                <option value="Rejected">Rejected</option>
                <option value="Unavailable">Unavailable</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-ink-soft">
              <span>Product:</span>
              <select
                value={productFilter}
                onChange={(e) => setProductFilter(e.target.value)}
                aria-label="Filter by product scope"
                className="bg-paper border border-line rounded px-2 py-1 text-xs text-ink focus:outline-none focus:border-accent"
              >
                <option value="All">All Products</option>
                <option value="Northstar Cloud">Northstar Cloud</option>
                <option value="Enterprise Suite">Enterprise Suite</option>
                <option value="GovCloud">GovCloud</option>
              </select>
            </div>

            {(search || statusFilter !== "All" || productFilter !== "All") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearFilters}
                className="text-xs h-7 text-ink-mute hover:text-ink"
              >
                <X className="w-3 h-3 mr-1" /> Clear
              </Button>
            )}
          </div>
        </div>

        {/* Evidence Table */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="p-4 rounded-lg bg-surface border border-line flex items-center justify-between">
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
                <Skeleton className="h-8 w-24" />
              </div>
            ))}
          </div>
        ) : evidenceList.length === 0 ? (
          <EmptyState
            icon={<FileSpreadsheet className="w-8 h-8" />}
            title="No evidence documents found"
            description={
              search || statusFilter !== "All" || productFilter !== "All"
                ? "No evidence matching the current filter criteria."
                : "Upload your first corporate policy, audit certificate, or spec sheet to power CitationGate verification."
            }
            action={
              <Button size="sm" onClick={() => setUploadModalOpen(true)} className="bg-accent hover:bg-accent-hover text-ink text-xs">
                <Upload className="w-3.5 h-3.5 mr-1.5" />
                Upload Evidence
              </Button>
            }
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-line bg-surface">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-ink">
                <thead className="border-b border-line bg-sunken/40 font-medium text-ink-mute">
                  <tr>
                    <th className="py-3 px-4">Document</th>
                    <th className="py-3 px-4">Status & Validity</th>
                    <th className="py-3 px-4">Scope</th>
                    <th className="py-3 px-4">Evaluations</th>
                    <th className="py-3 px-4">Uploaded</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {evidenceList.map((item) => {
                    const statusBadge = getEvidenceStatusBadge(item.status, item.is_expired);
                    const ext = item.filename.split(".").pop()?.toLowerCase();

                    return (
                      <tr key={item.id} className="hover:bg-sunken/30 transition-colors">
                        {/* Title and file metadata */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-start gap-3">
                            <div className="p-2 rounded bg-paper border border-line shrink-0">
                              {getFileIcon(item.file_type || item.mime_type || "", ext)}
                            </div>
                            <div className="space-y-0.5">
                              <button
                                onClick={() => handleOpenDetail(item.id)}
                                className="font-medium text-ink hover:text-accent-ink hover:underline text-left"
                              >
                                {item.title}
                              </button>
                              <div className="flex items-center gap-2 text-[11px] text-ink-soft">
                                <span className="font-mono">{item.filename}</span>
                                <span>•</span>
                                <span>{formatBytes(item.file_size)}</span>
                                {item.source_reference && (
                                  <>
                                    <span>•</span>
                                    <span className="truncate max-w-[180px]">{item.source_reference}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Status & Validity */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <div className="space-y-1">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${statusBadge.colorClass}`}
                            >
                              {statusBadge.icon === "check" && <CheckCircle2 className="w-3 h-3" />}
                              {statusBadge.icon === "alert" && <AlertTriangle className="w-3 h-3" />}
                              {statusBadge.icon === "x" && <XCircle className="w-3 h-3" />}
                              {statusBadge.icon === "clock" && <Clock className="w-3 h-3" />}
                              {statusBadge.icon === "shield" && <ShieldAlert className="w-3 h-3" />}
                              <span>{statusBadge.label}</span>
                            </span>
                            {item.expires_at && (
                              <div className="text-[10px] text-ink-mute flex items-center gap-1">
                                <Calendar className="w-2.5 h-2.5" />
                                <span>
                                  {item.is_expired
                                    ? `Expired ${formatDate(item.expires_at)}`
                                    : `Expires ${formatDate(item.expires_at)}`}
                                </span>
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Scopes */}
                        <td className="py-3.5 px-4">
                          <div className="flex flex-wrap gap-1 text-[11px]">
                            <span className="px-1.5 py-0.5 rounded bg-paper border border-line text-ink-soft">
                              {item.product_scope || "All Products"}
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-paper border border-line text-ink-mute">
                              {item.region_scope || "Global"}
                            </span>
                          </div>
                        </td>

                        {/* Evaluations */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          {item.associated_review_ids && item.associated_review_ids.length > 0 ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-accent-ink bg-accent-soft px-2 py-0.5 rounded border border-accent/20">
                              <LinkIcon className="w-3 h-3" />
                              {item.associated_review_ids.length} linked
                            </span>
                          ) : (
                            <span className="text-[11px] text-ink-mute">Unlinked</span>
                          )}
                        </td>

                        {/* Uploaded date & Owner */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <div className="space-y-0.5">
                            <span className="text-[11px] text-ink block">{formatRelativeTime(item.created_at)}</span>
                            <span className="text-[10px] text-ink-mute block">{item.uploader_name || item.uploaded_by_name || "Author"}</span>
                          </div>
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDownload(item.id, item.filename)}
                              isLoading={downloadingId === item.id}
                              title="Download authenticated file"
                              className="h-7 px-2 border-line-strong hover:bg-sunken text-xs text-ink"
                            >
                              <Download className="w-3 h-3" />
                            </Button>

                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setTargetEvidenceId(item.id);
                                setAssociateModalOpen(true);
                              }}
                              title="Link to Evaluation"
                              className="h-7 px-2 border-line-strong hover:bg-sunken text-xs text-ink"
                            >
                              <LinkIcon className="w-3 h-3" />
                            </Button>

                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenDetail(item.id)}
                              title="Inspect Details"
                              className="h-7 px-2 border-line-strong hover:bg-sunken text-xs text-ink"
                            >
                              <Eye className="w-3 h-3" />
                            </Button>

                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteEvidence(item.id, item.title)}
                              title="Delete Evidence"
                              className="h-7 px-2 text-ink-mute hover:text-rose-400 hover:bg-rose-500/10"
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* UPLOAD EVIDENCE MODAL */}
        {uploadModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-line">
                <div className="flex items-center gap-2">
                  <Upload className="w-5 h-5 text-accent-ink" />
                  <h3 className="text-base font-semibold text-ink">Upload Corporate Evidence</h3>
                </div>
                <button
                  onClick={() => setUploadModalOpen(false)}
                  className="rounded-lg p-1 text-ink-mute hover:text-ink hover:bg-sunken"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
                {/* File picker */}
                <div>
                  <label className="block font-medium text-ink mb-1.5">
                    Supporting Document <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
                    onChange={handleFileChange}
                    className="w-full px-3 py-2 bg-paper border border-line rounded-lg text-xs text-ink file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-accent-soft file:text-accent-ink hover:file:bg-accent focus:outline-none"
                  />
                  <p className="text-[11px] text-ink-mute mt-1">
                    PDF, DOCX, TXT, PNG, JPG/JPEG up to 15 MB. Deep content inspection will verify magic bytes.
                  </p>
                </div>

                {/* Title */}
                <div>
                  <label className="block font-medium text-ink mb-1">
                    Document Title <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Q3 SOC-2 Type II Compliance Report"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    className="w-full px-3 py-2 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block font-medium text-ink mb-1">Description (Optional)</label>
                  <textarea
                    rows={2}
                    placeholder="Summary of certified claims, audit methodology, or benchmark standards..."
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                    className="w-full px-3 py-2 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                {/* Scopes Grid */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block font-medium text-ink mb-1">Product Scope</label>
                    <select
                      value={uploadProduct}
                      onChange={(e) => setUploadProduct(e.target.value)}
                      className="w-full px-2 py-1.5 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="All">All Products</option>
                      <option value="Northstar Cloud">Northstar Cloud</option>
                      <option value="Enterprise Suite">Enterprise Suite</option>
                      <option value="GovCloud">GovCloud</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-medium text-ink mb-1">Region Scope</label>
                    <select
                      value={uploadRegion}
                      onChange={(e) => setUploadRegion(e.target.value)}
                      className="w-full px-2 py-1.5 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="Global">Global</option>
                      <option value="North America">North America</option>
                      <option value="EU">EU / UK</option>
                      <option value="APAC">APAC</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-medium text-ink mb-1">Expiry Date</label>
                    <input
                      type="date"
                      value={uploadExpiresAt}
                      onChange={(e) => setUploadExpiresAt(e.target.value)}
                      className="w-full px-2 py-1.5 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>

                {/* Source reference */}
                <div>
                  <label className="block font-medium text-ink mb-1">
                    Citation Reference Note (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Section 4.2, Table 7 on page 19"
                    value={uploadSourceRef}
                    onChange={(e) => setUploadSourceRef(e.target.value)}
                    className="w-full px-3 py-2 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                {/* Optional Evaluation to link */}
                <div>
                  <label className="block font-medium text-ink mb-1">
                    Associate with Review / Evaluation (Optional)
                  </label>
                  <select
                    value={uploadReviewId}
                    onChange={(e) => setUploadReviewId(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="">Do not associate now (general corporate library)</option>
                    {availableReviews.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title || r.document_title || "Untitled Draft"} (v{r.version_id?.slice(0, 6) || 1})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Progress bar */}
                {uploadProgress !== null && (
                  <div className="space-y-1">
                    <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-accent h-1.5 transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-ink-mute block text-right">
                      {uploadProgress < 100 ? "Validating & Uploading..." : "Finalizing..."}
                    </span>
                  </div>
                )}

                {/* Buttons */}
                <div className="flex items-center justify-end gap-2 pt-3 border-t border-line">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setUploadModalOpen(false)}
                    className="border-line-strong hover:bg-sunken text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    isLoading={uploading}
                    className="bg-accent hover:bg-accent-hover text-ink text-xs font-semibold"
                  >
                    Upload & Validate
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ASSOCIATE EVALUATION MODAL */}
        {associateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-line">
                <div className="flex items-center gap-2">
                  <LinkIcon className="w-4 h-4 text-accent-ink" />
                  <h3 className="text-base font-semibold text-ink">Link Evidence to Evaluation</h3>
                </div>
                <button
                  onClick={() => setAssociateModalOpen(false)}
                  className="rounded-lg p-1 text-ink-mute hover:text-ink hover:bg-sunken"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleAssociateSubmit} className="space-y-4 text-xs">
                <p className="text-ink-soft">
                  Select an evaluation to associate this evidence with. Once linked, CitationGate will consider this document as valid factual support during claim verification.
                </p>

                <div>
                  <label className="block font-medium text-ink mb-1.5">Target Evaluation</label>
                  <select
                    value={selectedReviewId}
                    onChange={(e) => setSelectedReviewId(e.target.value)}
                    required
                    className="w-full px-2.5 py-2 bg-paper border border-line rounded-lg text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="">Select an evaluation...</option>
                    {availableReviews.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title || r.document_title || "Untitled Draft"} ({r.product || "Global"})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-line">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setAssociateModalOpen(false)}
                    className="border-line-strong hover:bg-sunken text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    isLoading={associating}
                    className="bg-accent hover:bg-accent-hover text-ink text-xs font-semibold"
                  >
                    Link Evidence
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* EVIDENCE DETAIL SLIDE-OVER / DRAWER */}
        {selectedEvidence && (
          <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-xl h-full bg-surface border-l border-line p-6 overflow-y-auto space-y-6 shadow-2xl">
              {/* Header */}
              <div className="flex items-start justify-between pb-4 border-b border-line">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${
                        getEvidenceStatusBadge(selectedEvidence.status, selectedEvidence.is_expired).colorClass
                      }`}
                    >
                      {selectedEvidence.status}
                    </span>
                    {selectedEvidence.is_expired && (
                      <span className="text-[11px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-semibold border border-rose-500/40">
                        Expired
                      </span>
                    )}
                  </div>
                  <h2 className="text-xl font-semibold text-ink mt-1">{selectedEvidence.title}</h2>
                  <p className="text-xs text-ink-soft">
                    {selectedEvidence.filename} • {formatBytes(selectedEvidence.file_size)}
                  </p>
                </div>

                <button
                  onClick={() => setSelectedEvidence(null)}
                  className="rounded-lg p-1.5 text-ink-mute hover:text-ink hover:bg-sunken"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDownload(selectedEvidence.id, selectedEvidence.filename)}
                  isLoading={downloadingId === selectedEvidence.id}
                  className="border-line-strong hover:bg-sunken text-xs text-ink"
                >
                  <Download className="w-3.5 h-3.5 mr-1.5" />
                  Download File
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setTargetEvidenceId(selectedEvidence.id);
                    setAssociateModalOpen(true);
                  }}
                  className="border-line-strong hover:bg-sunken text-xs text-ink"
                >
                  <LinkIcon className="w-3.5 h-3.5 mr-1.5" />
                  Link to Evaluation
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleDeleteEvidence(selectedEvidence.id, selectedEvidence.title)}
                  className="text-xs text-ink-mute hover:text-rose-400 hover:bg-rose-500/10 ml-auto"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                  Delete
                </Button>
              </div>

              {/* Validation Alert if errors */}
              {selectedEvidence.validation_errors && (
                <div className="p-3.5 rounded-lg bg-rose-950/40 border border-rose-600/40 text-xs text-rose-200 space-y-1.5">
                  <div className="flex items-center gap-2 font-semibold text-rose-100">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span>CitationGate Validation Errors</span>
                  </div>
                  <p className="text-rose-300 whitespace-pre-wrap">{selectedEvidence.validation_errors}</p>
                </div>
              )}

              {/* Scopes & Metadata Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">Product Scope</span>
                  <span className="text-accent-ink font-medium block mt-0.5">
                    {selectedEvidence.product_scope || "All Products"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">Region Scope</span>
                  <span className="text-ink font-medium block mt-0.5">
                    {selectedEvidence.region_scope || "Global"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">Channel Scope</span>
                  <span className="text-ink font-medium block mt-0.5">
                    {selectedEvidence.channel_scope || "All Channels"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">Valid From</span>
                  <span className="text-ink font-medium block mt-0.5">
                    {selectedEvidence.valid_from ? formatDate(selectedEvidence.valid_from) : "Immediate"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">Expires At</span>
                  <span
                    className={`font-medium block mt-0.5 ${
                      selectedEvidence.is_expired ? "text-rose-400 font-semibold" : "text-ink"
                    }`}
                  >
                    {selectedEvidence.expires_at ? formatDate(selectedEvidence.expires_at) : "Never (Permanent)"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-paper border border-line">
                  <span className="text-[11px] text-ink-mute block">File Type</span>
                  <span className="text-ink font-mono block mt-0.5 truncate">{selectedEvidence.file_type || selectedEvidence.mime_type}</span>
                </div>
              </div>

              {/* Checksum SHA-256 */}
              <div className="p-3 rounded-lg bg-paper border border-line text-xs space-y-1">
                <div className="flex items-center justify-between text-ink-mute">
                  <span className="flex items-center gap-1 font-mono text-[11px]">
                    <Hash className="w-3.5 h-3.5" /> SHA-256 Audit Checksum
                  </span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(selectedEvidence.sha256_checksum || selectedEvidence.file_hash || "");
                      setCopiedChecksum(true);
                      setTimeout(() => setCopiedChecksum(false), 2000);
                    }}
                    className="text-accent-ink hover:underline flex items-center gap-1 text-[11px]"
                  >
                    {copiedChecksum ? (
                      <>
                        <Check className="w-3 h-3" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" /> Copy Hash
                      </>
                    )}
                  </button>
                </div>
                <p className="font-mono text-[11px] text-ink break-all">
                  {selectedEvidence.sha256_checksum || selectedEvidence.file_hash || "No checksum computed"}
                </p>
              </div>

              {/* Description & Citation Note */}
              {selectedEvidence.description && (
                <div className="text-xs space-y-1">
                  <span className="text-ink-mute font-medium block">Description</span>
                  <p className="text-ink bg-paper p-3 rounded-lg border border-line">
                    {selectedEvidence.description}
                  </p>
                </div>
              )}

              {selectedEvidence.source_reference && (
                <div className="text-xs space-y-1">
                  <span className="text-ink-mute font-medium block">Source Reference / Citation Note</span>
                  <p className="text-ink bg-paper p-3 rounded-lg border border-line">
                    {selectedEvidence.source_reference}
                  </p>
                </div>
              )}

              {/* Extracted Text Snippet */}
              {selectedEvidence.extracted_text && (
                <div className="text-xs space-y-1">
                  <span className="text-ink-mute font-medium block">Extracted Text Content (Preview)</span>
                  <div className="bg-paper p-3 rounded-lg border border-line font-mono text-[11px] text-ink max-h-48 overflow-y-auto whitespace-pre-wrap">
                    {selectedEvidence.extracted_text}
                  </div>
                </div>
              )}

              {/* Associated Evaluations */}
              <div className="text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-ink">
                    Associated Evaluations ({selectedEvidence.associated_reviews?.length || 0})
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setTargetEvidenceId(selectedEvidence.id);
                      setAssociateModalOpen(true);
                    }}
                    className="text-accent-ink text-xs h-7 px-2 hover:bg-accent-soft"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Link Evaluation
                  </Button>
                </div>

                {!selectedEvidence.associated_reviews || selectedEvidence.associated_reviews.length === 0 ? (
                  <p className="text-ink-mute bg-paper p-3 rounded-lg border border-line">
                    This document is not currently associated with any specific marketing draft review.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {selectedEvidence.associated_reviews.map((rev) => (
                      <div
                        key={rev.review_id}
                        className="p-3 rounded-lg bg-paper border border-line flex items-center justify-between gap-3"
                      >
                        <div className="space-y-0.5">
                          <Link
                            href={`/reviews/${rev.review_id}`}
                            className="font-medium text-ink hover:text-accent-ink flex items-center gap-1.5"
                          >
                            <span>{rev.title || "Untitled Evaluation"}</span>
                            <ExternalLink className="w-3 h-3 text-ink-mute" />
                          </Link>
                          <span className="text-[11px] text-ink-soft">
                            Status: {rev.status} • Risk Score: {rev.risk_score}
                          </span>
                        </div>

                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleRemoveAssociation(selectedEvidence.id, rev.review_id)}
                          title="Unlink from evaluation"
                          className="h-7 px-2 text-ink-mute hover:text-rose-400 hover:bg-rose-500/10"
                        >
                          <Unlink className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Supported Claims */}
              <div className="text-xs space-y-2">
                <span className="font-semibold text-ink">
                  Supported Claims ({selectedEvidence.supported_claims?.length || 0})
                </span>
                {!selectedEvidence.supported_claims || selectedEvidence.supported_claims.length === 0 ? (
                  <p className="text-ink-mute bg-paper p-3 rounded-lg border border-line">
                    No marketing claims have been formally mapped to this evidence document yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {selectedEvidence.supported_claims.map((c, i) => (
                      <div key={c.claim_id || i} className="p-3 rounded-lg bg-paper border border-line space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[11px] text-accent-ink">{c.claim_id || "CLAIM"}</span>
                          <span className="text-[11px] text-emerald-400 font-medium">{c.status}</span>
                        </div>
                        <p className="text-ink font-medium">{c.claim_text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
