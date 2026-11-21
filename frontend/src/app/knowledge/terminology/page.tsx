"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Layers,
  Plus,
  Trash2,
  ArrowRight,
  Ban,
  CheckCircle2,
  Upload,
  Search,
  Archive,
  Download,
  X,
  FileText,
  Filter,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { Term, CsvImportResult } from "@/lib/types";

export default function TerminologyPage() {
  const { user } = useAuth();
  const { success, error, warning } = useToast();

  const [terms, setTerms] = useState<Term[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [approvedTerm, setApprovedTerm] = useState("");
  const [disallowedInput, setDisallowedInput] = useState("");
  const [replacement, setReplacement] = useState("");
  const [notes, setNotes] = useState("");
  const [productScope, setProductScope] = useState("All");
  const [regionScope, setRegionScope] = useState("Global");
  const [channelScope, setChannelScope] = useState("All");
  const [saving, setSaving] = useState(false);

  // CSV Import Modal
  const [csvModalOpen, setCsvModalOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<CsvImportResult | null>(null);

  const fetchTerms = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.terms.list({
        q: search || undefined,
        status: statusFilter === "All" ? undefined : statusFilter,
      });
      setTerms(res);
    } catch (err: any) {
      error("Failed to load terminology", err.message);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, error]);

  useEffect(() => {
    fetchTerms();
  }, [fetchTerms]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!approvedTerm.trim()) {
      error("Missing term", "Approved term is required.");
      return;
    }
    setSaving(true);
    try {
      const disallowedList = disallowedInput
        .split(/[,|;]/)
        .map((s) => s.trim())
        .filter(Boolean);

      await api.terms.create({
        approved_term: approvedTerm.trim(),
        disallowed_variants: disallowedList,
        replacement: replacement.trim() || approvedTerm.trim(),
        notes: notes.trim() || undefined,
        product_scope: productScope || "All",
        region_scope: regionScope || "Global",
        channel_scope: channelScope || "All",
        status: "Approved",
        active: true,
      });

      success("Term Added", `Approved term '${approvedTerm}' registered.`);
      setCreateModalOpen(false);
      resetForm();
      fetchTerms();
    } catch (err: any) {
      error("Creation failed", err.message);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setApprovedTerm("");
    setDisallowedInput("");
    setReplacement("");
    setNotes("");
    setProductScope("All");
    setRegionScope("Global");
    setChannelScope("All");
  };

  const handleArchive = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to archive term '${name}'?`)) return;
    try {
      await api.terms.archive(id);
      success("Term Archived", `Archived '${name}'.`);
      fetchTerms();
    } catch (err: any) {
      error("Archive failed", err.message);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      warning("No file selected", "Please select a CSV file.");
      return;
    }
    setCsvUploading(true);
    try {
      const res = await api.terms.importCsv(csvFile);
      setCsvResult(res);
      if (res.imported_count > 0) {
        success("CSV Import Completed", `Successfully imported ${res.imported_count} terms.`);
        fetchTerms();
      } else {
        warning("Import Incomplete", "No terms imported. Check errors below.");
      }
    } catch (err: any) {
      error("CSV Import Failed", err.message);
    } finally {
      setCsvUploading(false);
    }
  };

  const downloadSampleCsv = () => {
    const csvContent =
      "approved_term,disallowed_variants,replacement,notes,product_scope,region_scope,channel_scope\n" +
      "BrandProof,Brand Proof|Brand-Proof|brandproof,BrandProof,CamelCase single word only,All,Global,All\n" +
      "Northstar Pro,Northstar Premium|Northstar Plus,Northstar Pro,Product line nomenclature,Northstar Pro,Global,All\n" +
      "Autonomous Agents,Self-Running Bots|Auto Bots,Autonomous Agents,Enterprise AI naming standard,All,Global,All\n";

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "brandproof_terms_sample.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const canManage = user?.role === "Brand Manager" || user?.role === "Admin";

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Terminology</h1>
            <p className="text-xs text-ink-soft mt-1">
              Approved names, trademark rules and disallowed variants.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {canManage && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setCsvResult(null);
                    setCsvFile(null);
                    setCsvModalOpen(true);
                  }}
                  className="bg-surface border-line-strong hover:bg-sunken text-ink"
                >
                  <Upload className="w-3.5 h-3.5 mr-1.5" />
                  <span>Import CSV</span>
                </Button>

                <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                  <Plus className="w-4 h-4 mr-1.5" />
                  <span>Add Approved Term</span>
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3.5 rounded-lg bg-surface border border-line">
          <div className="relative w-full sm:w-80">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search approved or disallowed terms..."
              className="w-full bg-paper border border-line-strong rounded-lg pl-8 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">All Statuses</option>
              <option value="Approved">Approved</option>
              <option value="Archived">Archived</option>
            </select>
          </div>
        </div>

        {/* Terminology Cards */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
        ) : terms.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {terms.map((term) => (
              <Card
                key={term.id}
                className={`p-4 bg-surface border transition-colors flex flex-col justify-between space-y-3 ${
                  term.status === "Archived" ? "opacity-60 border-line" : "border-line hover:border-line-strong"
                }`}
              >
                <div className="space-y-3">
                  {/* Approved Term Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <h3 className="font-semibold text-sm text-ink font-mono">{term.approved_term || term.term}</h3>
                    </div>
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Approved
                    </span>
                  </div>

                  {/* Disallowed Variants */}
                  {term.disallowed_variants && term.disallowed_variants.length > 0 ? (
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-medium text-ink-soft flex items-center gap-1">
                        <Ban className="w-3 h-3 text-rose-400" /> Disallowed Variants:
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {term.disallowed_variants.map((v, i) => (
                          <span
                            key={i}
                            className="text-[11px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20"
                          >
                            {v}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-ink-mute italic">No disallowed variants specified</div>
                  )}

                  {/* Replacement guidance */}
                  {term.replacement && term.replacement !== (term.approved_term || term.term) && (
                    <div className="text-[11px] text-ink flex items-center gap-1.5 p-2 rounded bg-paper border border-line">
                      <ArrowRight className="w-3 h-3 text-accent-ink shrink-0" />
                      <span>Replace with: <strong className="text-emerald-400">{term.replacement}</strong></span>
                    </div>
                  )}

                  {/* Notes & Scopes */}
                  <div className="space-y-1 text-[11px] text-ink-soft">
                    {term.notes && (
                      <p className="text-ink-soft italic bg-paper p-2 rounded border border-line">
                        &ldquo;{term.notes}&rdquo;
                      </p>
                    )}
                    <div className="flex justify-between pt-1">
                      <span className="text-ink-mute">Scope:</span>
                      <span className="text-ink">
                        {term.product_scope || "All"} • {term.region_scope || "Global"} • {term.channel_scope || "All"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] text-ink-mute">
                  <span>Status: {term.status || "Approved"}</span>
                  {canManage && term.status !== "Archived" && (
                    <button
                      onClick={() => handleArchive(term.id, term.approved_term || term.term || "term")}
                      className="text-ink-mute hover:text-rose-400 flex items-center gap-1 transition-colors"
                    >
                      <Archive className="w-3.5 h-3.5" />
                      <span>Archive</span>
                    </button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Layers className="w-6 h-6" />}
            title="No terminology records found"
            description="No brand terms match your active filter."
            action={
              canManage ? (
                <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                  Add Approved Term
                </Button>
              ) : undefined
            }
          />
        )}

        {/* Create Term Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
            <div className="bg-surface border border-line rounded-xl w-full max-w-lg p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h2 className="text-base font-semibold text-ink">Add Approved Term</h2>
                <button onClick={() => setCreateModalOpen(false)} className="text-ink-soft hover:text-ink">✕</button>
              </div>

              <form onSubmit={handleCreate} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Approved Term *</label>
                  <input
                    type="text"
                    required
                    value={approvedTerm}
                    onChange={(e) => setApprovedTerm(e.target.value)}
                    placeholder="e.g. Northstar Pro"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Disallowed Variants (Comma or pipe separated)
                  </label>
                  <input
                    type="text"
                    value={disallowedInput}
                    onChange={(e) => setDisallowedInput(e.target.value)}
                    placeholder="e.g. Northstar Premium, Northstar Plus, North-star Pro"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Auto-Replacement Suggestion (Optional)
                  </label>
                  <input
                    type="text"
                    value={replacement}
                    onChange={(e) => setReplacement(e.target.value)}
                    placeholder="e.g. Northstar Pro"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Usage Notes / Guidance</label>
                  <input
                    type="text"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="e.g. Capitalize Pro; never abbreviate to NS-P."
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">Product Scope</label>
                    <input
                      type="text"
                      value={productScope}
                      onChange={(e) => setProductScope(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">Region Scope</label>
                    <input
                      type="text"
                      value={regionScope}
                      onChange={(e) => setRegionScope(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">Channel Scope</label>
                    <input
                      type="text"
                      value={channelScope}
                      onChange={(e) => setChannelScope(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2.5 pt-3 border-t border-line">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setCreateModalOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={saving}>
                    {saving ? "Registering..." : "Add Term"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* CSV Import Modal */}
        {csvModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
            <div className="bg-surface border border-line rounded-xl w-full max-w-xl p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2">
                  <Upload className="w-4 h-4 text-accent-ink" />
                  <h2 className="text-base font-semibold text-ink">Import Terminology CSV</h2>
                </div>
                <button onClick={() => setCsvModalOpen(false)} className="text-ink-soft hover:text-ink">✕</button>
              </div>

              <div className="p-3.5 rounded-lg bg-paper border border-line space-y-2 text-xs">
                <div className="font-semibold text-ink">Expected CSV Header Format:</div>
                <code className="block p-2 rounded bg-surface text-[11px] text-emerald-400 font-mono break-all border border-line">
                  approved_term,disallowed_variants,replacement,notes,product_scope,region_scope,channel_scope
                </code>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11px] text-ink-soft">Separate multiple disallowed variants with &apos;|&apos; or comma</span>
                  <button
                    onClick={downloadSampleCsv}
                    className="text-[11px] text-accent-ink hover:text-accent-ink flex items-center gap-1 font-medium"
                  >
                    <Download className="w-3 h-3" /> Download Sample CSV
                  </button>
                </div>
              </div>

              <form onSubmit={handleCsvUpload} className="space-y-4">
                <div className="border-2 border-dashed border-line hover:border-line-strong rounded-lg p-6 text-center cursor-pointer bg-paper">
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-ink-soft file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-accent file:text-ink hover:file:bg-accent cursor-pointer"
                  />
                  {csvFile && (
                    <div className="mt-2 text-xs text-emerald-400 flex items-center justify-center gap-1">
                      <FileText className="w-3.5 h-3.5" /> Selected: {csvFile.name} ({(csvFile.size / 1024).toFixed(1)} KB)
                    </div>
                  )}
                </div>

                {csvResult && (
                  <div
                    className={`p-3.5 rounded-lg text-xs space-y-2 border ${
                      csvResult.imported_count > 0
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                        : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                    }`}
                  >
                    <div className="font-semibold flex items-center justify-between">
                      <span>Imported: {csvResult.imported_count} terms</span>
                      <span>Errors: {csvResult.errors.length}</span>
                    </div>

                    {csvResult.errors.length > 0 && (
                      <div className="max-h-32 overflow-y-auto space-y-1 p-2 rounded bg-ink/30 text-[11px] font-mono text-rose-300">
                        {csvResult.errors.map((err, i) => (
                          <div key={i}>• {err}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end gap-2.5 pt-2 border-t border-line">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setCsvModalOpen(false)}>
                    Close
                  </Button>
                  <Button type="submit" size="sm" disabled={csvUploading || !csvFile}>
                    {csvUploading ? "Uploading..." : "Import Terminology"}
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
