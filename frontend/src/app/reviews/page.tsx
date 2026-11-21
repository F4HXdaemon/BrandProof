"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  FileCheck2,
  FilePlus,
  Filter,
  ArrowRight,
  RefreshCw,
  Search,
  Globe,
  Tag,
  Shield,
  AlertTriangle,
  User,
  SlidersHorizontal,
  X,
  Edit3,
  Trash2,
  Download,
  FileCode,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { Review, ReviewStatus } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

export default function ReviewsPage() {
  const { success, error } = useToast();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [productFilter, setProductFilter] = useState<string>("All");
  const [regionFilter, setRegionFilter] = useState<string>("All");
  const [channelFilter, setChannelFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [submittedQuery, setSubmittedQuery] = useState<string>("");

  // Rename Modal State
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [editingReview, setEditingReview] = useState<Review | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [savingRename, setSavingRename] = useState(false);

  // Delete Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingReview, setDeletingReview] = useState<Review | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Re-run State
  const [reEvaluatingId, setReEvaluatingId] = useState<string | null>(null);
  const [downloadingReportId, setDownloadingReportId] = useState<string | null>(null);
  const [downloadingJsonId, setDownloadingJsonId] = useState<string | null>(null);

  const handleDownloadReport = async (reviewId: string, title?: string) => {
    setDownloadingReportId(reviewId);
    try {
      const clean = (title || "review").toLowerCase().replace(/[^a-z0-9_-]/g, "_");
      await api.reviews.downloadReport(reviewId, `${clean}_audit_report.pdf`);
      success("Report Downloaded", "Audit report downloaded successfully.");
    } catch (err: any) {
      error("Report Failed", err.message || "Failed to download audit report.");
    } finally {
      setDownloadingReportId(null);
    }
  };

  const handleDownloadReportJson = async (reviewId: string, title?: string) => {
    setDownloadingJsonId(reviewId);
    try {
      const data = await api.reviews.getReportJson(reviewId);
      const clean = (title || "review").toLowerCase().replace(/[^a-z0-9_-]/g, "_");
      const filename = `${clean}_audit_report.json`;
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      success("JSON Report Downloaded", "Audit report JSON downloaded successfully.");
    } catch (err: any) {
      error("Export Failed", err.message || "Failed to download audit JSON.");
    } finally {
      setDownloadingJsonId(null);
    }
  };

  const handleOpenRename = (r: Review) => {
    setEditingReview(r);
    setEditTitle(r.title || r.document_title || "");
    setRenameModalOpen(true);
  };

  const handleSaveRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingReview || !editTitle.trim()) return;
    setSavingRename(true);
    try {
      await api.reviews.update(editingReview.id, { title: editTitle.trim() });
      setReviews((prev) =>
        prev.map((r) => (r.id === editingReview.id ? { ...r, title: editTitle.trim() } : r))
      );
      success("Review Renamed", `Review renamed to "${editTitle.trim()}".`);
      setRenameModalOpen(false);
      setEditingReview(null);
    } catch (err: any) {
      error("Rename Failed", err.message || "Failed to rename review.");
    } finally {
      setSavingRename(false);
    }
  };

  const handleReRun = async (reviewId: string) => {
    setReEvaluatingId(reviewId);
    try {
      const res = await api.reviews.reEvaluate(reviewId);
      setReviews((prev) =>
        prev.map((r) =>
          r.id === reviewId
            ? { ...r, status: res.status, risk_score: res.risk_score, risk_level: res.risk_level }
            : r
        )
      );
      success("Audit Re-run Completed", "Brand governance audit re-executed successfully.");
      fetchReviews();
    } catch (err: any) {
      error("Re-run Failed", err.message || "Failed to re-run review audit.");
    } finally {
      setReEvaluatingId(null);
    }
  };

  const handleOpenDelete = (r: Review) => {
    setDeletingReview(r);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingReview) return;
    setIsDeleting(true);
    try {
      await api.reviews.delete(deletingReview.id);
      setReviews((prev) => prev.filter((r) => r.id !== deletingReview.id));
      success("Review Deleted", `Review "${deletingReview.title || "Untitled"}" deleted successfully.`);
      setDeleteModalOpen(false);
      setDeletingReview(null);
    } catch (err: any) {
      error("Delete Failed", err.message || "Failed to delete review.");
    } finally {
      setIsDeleting(false);
    }
  };

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.reviews.list({
        status: statusFilter === "All" ? undefined : statusFilter,
        product: productFilter === "All" ? undefined : productFilter,
        region: regionFilter === "All" ? undefined : regionFilter,
        channel: channelFilter === "All" ? undefined : channelFilter,
        q: submittedQuery.trim() || undefined,
      });
      setReviews(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, productFilter, regionFilter, channelFilter, submittedQuery]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery === submittedQuery) {
      fetchReviews();
    } else {
      setSubmittedQuery(searchQuery);
    }
  };

  const clearFilters = () => {
    setStatusFilter("All");
    setProductFilter("All");
    setRegionFilter("All");
    setChannelFilter("All");
    setSearchQuery("");
    setSubmittedQuery("");
  };

  const hasActiveFilters =
    statusFilter !== "All" ||
    productFilter !== "All" ||
    regionFilter !== "All" ||
    channelFilter !== "All" ||
    searchQuery.trim().length > 0;

  const statuses: ("All" | ReviewStatus | "Failed")[] = [
    "All",
    "Needs Review",
    "In Progress",
    "Approved",
    "Changes Requested",
    "Rejected",
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Reviews</h1>
            <p className="text-xs text-ink-soft mt-1">
              Drafts waiting for verification and sign-off.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <Button variant="outline" size="sm" onClick={fetchReviews} isLoading={loading}>
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </Button>
            <Link href="/reviews/new">
              <Button size="sm">
                <FilePlus className="w-4 h-4" />
                <span>New Review</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="space-y-3 bg-surface p-3.5 rounded-lg border border-line">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            {/* Search Input */}
            <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-ink-mute" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search reviews by title, purpose, or draft keywords..."
                className="w-full bg-paper border border-line-strong rounded-lg pl-9 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
              />
            </form>

            {/* Product Filter */}
            <select
              value={productFilter}
              onChange={(e) => setProductFilter(e.target.value)}
              className="w-full sm:w-auto bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">All Products</option>
              <option value="Northstar Pro">Northstar Pro</option>
              <option value="Northstar Sovereign Cloud">Northstar Sovereign Cloud</option>
              <option value="CloudShield Intelligence">CloudShield Intelligence</option>
            </select>

            {/* Region Filter */}
            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
              className="w-full sm:w-auto bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">All Regions</option>
              <option value="India">India</option>
              <option value="Global">Global</option>
              <option value="North America">North America</option>
              <option value="European Union">European Union</option>
              <option value="Asia Pacific">Asia Pacific</option>
            </select>

            {/* Channel Filter */}
            <select
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              className="w-full sm:w-auto bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">All Channels</option>
              <option value="Advertisement">Advertisement</option>
              <option value="Website & Landing Page">Website & Landing Page</option>
              <option value="Press Release">Press Release</option>
              <option value="Sales Collateral">Sales Collateral</option>
              <option value="Whitepaper">Technical Whitepaper</option>
            </select>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs text-ink-soft hover:text-ink flex items-center gap-1 shrink-0 px-2 py-1"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>
            )}
          </div>

          {/* Status Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pt-2 border-t border-line">
            <span className="text-[11px] font-medium text-ink-mute mr-1 shrink-0 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Status:
            </span>
            {statuses.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                  statusFilter === s
                    ? "bg-accent text-ink "
                    : "text-ink-soft hover:text-ink hover:bg-sunken"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Reviews List */}
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : reviews.length > 0 ? (
          <div className="grid grid-cols-1 gap-3">
            {reviews.map((r) => {
              const displayTitle = r.title || r.document_title || "Draft Document";
              const productScope = r.product || "All Products";
              const regionScope = r.region || "Global";
              const channelScope = r.channel || "All Channels";

              return (
                <Card
                  key={r.id}
                  className="hover:border-line-strong transition-all p-4 bg-surface"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="space-y-2 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-sm text-ink hover:text-accent-ink transition-colors">
                          <Link href={`/reviews/${r.id}`}>{displayTitle}</Link>
                        </h3>
                        <Badge variant="status" value={r.status} />

                        {r.processing_status && r.processing_status !== "Ready" && (
                          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            {r.processing_status}
                          </span>
                        )}

                        {r.risk_level && (
                          <span
                            className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
                              r.risk_level === "High"
                                ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                                : r.risk_level === "Medium"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            }`}
                          >
                            {r.risk_level} Risk
                          </span>
                        )}
                      </div>

                      {/* Scopes Pill Row */}
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-soft">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-paper border border-line text-accent-ink">
                          <Tag className="w-3 h-3 text-accent-ink" />
                          {productScope}
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-paper border border-line text-ink">
                          <Globe className="w-3 h-3 text-cyan-400" />
                          {regionScope}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-paper border border-line text-ink-soft">
                          {channelScope}
                        </span>
                        {r.content_type && (
                          <span className="px-2 py-0.5 rounded bg-paper border border-line text-ink-mute">
                            {r.content_type}
                          </span>
                        )}
                      </div>

                      {/* Summary or Purpose */}
                      <p className="text-xs text-ink-soft line-clamp-1">
                        {r.purpose ? `Intent: ${r.purpose}` : r.summary}
                      </p>

                      {/* Meta Footer */}
                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-mute pt-0.5">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3 text-ink-soft" />
                          Creator: {r.creator_name || "Enterprise Creator"}
                        </span>
                        <span>•</span>
                        <span>Reviewer: {r.reviewer_name || "Unassigned"}</span>
                        <span>•</span>
                        <span
                          className={
                            r.findings_count > 0 ? "text-amber-400 font-medium" : "text-emerald-400"
                          }
                        >
                          {r.findings_count} findings flagged
                        </span>
                        <span>•</span>
                        <span>{r.claims_count || 0} claims detected</span>
                        <span>•</span>
                        <span>Updated {formatRelativeTime(r.updated_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 self-end lg:self-center shrink-0">
                      {/* Re-run button */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleReRun(r.id)}
                        isLoading={reEvaluatingId === r.id}
                        className="text-xs border-line-strong text-ink hover:bg-sunken h-8 px-2.5"
                        title="Re-run Brand Audit"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 text-accent-ink ${reEvaluatingId === r.id ? "animate-spin" : ""}`} />
                      </Button>

                      {/* Rename button */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleOpenRename(r)}
                        className="text-xs border-line-strong text-ink hover:bg-sunken h-8 px-2.5"
                        title="Rename Review"
                      >
                        <Edit3 className="w-3.5 h-3.5 text-ink-soft hover:text-ink" />
                      </Button>

                      {/* Download Report */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownloadReport(r.id, r.title)}
                        isLoading={downloadingReportId === r.id}
                        className="text-xs border-line-strong text-ink hover:bg-sunken h-8 px-2.5"
                        title="Download PDF Report"
                      >
                        <Download className="w-3.5 h-3.5 mr-1 text-accent-ink" />
                        PDF
                      </Button>

                      {/* Export JSON */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownloadReportJson(r.id, r.title)}
                        isLoading={downloadingJsonId === r.id}
                        className="text-xs border-line-strong text-purple-400 hover:bg-purple-950/20 h-8 px-2.5"
                        title="Export Audit JSON"
                      >
                        <FileCode className="w-3.5 h-3.5 mr-1 text-purple-400" />
                        JSON
                      </Button>

                      {/* Delete button */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleOpenDelete(r)}
                        className="text-xs border-line-strong text-rose-400 hover:bg-rose-950/40 hover:border-rose-800 h-8 px-2.5"
                        title="Delete Review"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>

                      <Link href={`/reviews/${r.id}`}>
                        <Button size="sm" variant="secondary" className="h-8 text-xs font-semibold px-3">
                          Workspace <ArrowRight className="w-3.5 h-3.5 ml-1" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={<FileCheck2 className="w-6 h-6 text-accent-ink" />}
            title="No reviews match your filters"
            description="Adjust your search query or clear scopes to view other documents in the governance queue."
            action={
              <div className="flex items-center gap-2">
                {hasActiveFilters && (
                  <Button size="sm" variant="outline" onClick={clearFilters}>
                    Clear Filters
                  </Button>
                )}
                <Link href="/reviews/new">
                  <Button size="sm">Submit New Draft</Button>
                </Link>
              </div>
            }
          />
        )}

        {/* Rename Review Modal */}
        {renameModalOpen && editingReview && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-surface border border-line rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
              <div className="flex items-center justify-between pb-3 border-b border-line">
                <h3 className="font-semibold text-sm text-ink flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-accent-ink" />
                  Rename Review
                </h3>
                <button
                  type="button"
                  onClick={() => setRenameModalOpen(false)}
                  className="text-ink-mute hover:text-ink transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleSaveRename} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-ink">
                    Review Title <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="mt-1.5 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                    placeholder="Enter new review title..."
                  />
                  <p className="text-[11px] text-ink-mute mt-1">
                    Renaming updates the document title across workspace views.
                  </p>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setRenameModalOpen(false)}
                    className="text-xs border-line-strong text-ink hover:bg-sunken"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={savingRename || !editTitle.trim()}
                    className="text-xs bg-accent hover:bg-accent-hover text-ink font-semibold"
                  >
                    {savingRename ? "Saving..." : "Save Name"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Delete Review Confirmation Modal */}
        {deleteModalOpen && deletingReview && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-surface border border-rose-900/60 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
              <div className="flex items-center justify-between pb-3 border-b border-line">
                <h3 className="font-semibold text-sm text-rose-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  Delete Review
                </h3>
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="text-ink-mute hover:text-ink transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2 text-xs text-ink-soft">
                <p>
                  Are you sure you want to permanently delete{" "}
                  <strong className="text-ink">{deletingReview.title || "this review"}</strong>?
                </p>
                <p className="text-rose-300/80 bg-rose-950/40 p-2.5 rounded-lg border border-rose-900/50">
                  This will remove the review record, its claims ledger, CitationGate findings, and associated document artifacts from the organization.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setDeleteModalOpen(false)}
                  className="text-xs border-line-strong text-ink hover:bg-sunken"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={isDeleting}
                  onClick={handleConfirmDelete}
                  className="text-xs bg-rose-600 hover:bg-rose-500 text-white font-semibold"
                >
                  {isDeleting ? "Deleting..." : "Permanently Delete"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
