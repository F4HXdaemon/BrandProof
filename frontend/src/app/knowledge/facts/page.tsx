"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Database,
  Plus,
  Search,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Shield,
  Trash2,
  Upload,
  FileText,
  Filter,
  X,
  Copy,
  Check,
  Archive,
  Calendar,
  Layers,
  Globe,
  Tag,
  AlertCircle,
  Download,
  Sparkles,
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
import { Fact, FactStatus, CsvImportResult } from "@/lib/types";
import { formatDate, getFactExpiryBadge } from "@/lib/utils";
import { KnowledgeUploadModal } from "@/components/knowledge/knowledge-upload-modal";

export default function FactsPage() {
  const { user } = useAuth();
  const { success, error, warning } = useToast();

  const [facts, setFacts] = useState<Fact[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [productFilter, setProductFilter] = useState<string>("All");
  const [regionFilter, setRegionFilter] = useState<string>("All");
  const [channelFilter, setChannelFilter] = useState<string>("All");
  const [expiringOnly, setExpiringOnly] = useState(false);

  // Selected Fact for Detail Drawer
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);
  const [copiedValue, setCopiedValue] = useState(false);

  // Register New Fact Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [canonicalValue, setCanonicalValue] = useState("");
  const [description, setDescription] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [productScope, setProductScope] = useState("All");
  const [regionScope, setRegionScope] = useState("Global");
  const [channelScope, setChannelScope] = useState("All");
  const [validFrom, setValidFrom] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [statusVal, setStatusVal] = useState<FactStatus>("Approved");
  const [saving, setSaving] = useState(false);

  // Document / Image Ingestion Modal (Method B)
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  // CSV Import Modal
  const [csvModalOpen, setCsvModalOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<CsvImportResult | null>(null);

  const fetchFacts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.facts.list({
        q: search || undefined,
        status: statusFilter === "All" ? undefined : statusFilter,
        product_scope: productFilter === "All" ? undefined : productFilter,
        region_scope: regionFilter === "All" ? undefined : regionFilter,
        channel_scope: channelFilter === "All" ? undefined : channelFilter,
        expiring_soon: expiringOnly || undefined,
      });
      setFacts(res);
    } catch (err: any) {
      error("Failed to load facts", err.message);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, productFilter, regionFilter, channelFilter, expiringOnly, error]);

  useEffect(() => {
    fetchFacts();
  }, [fetchFacts]);

  const handleCreateFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !canonicalValue || !sourceReference) {
      error("Missing fields", "Title, canonical value, and source reference are strictly required.");
      return;
    }

    setSaving(true);
    try {
      await api.facts.create({
        title,
        canonical_value: canonicalValue,
        description: description || undefined,
        source_reference: sourceReference,
        product_scope: productScope || "All",
        region_scope: regionScope || "Global",
        channel_scope: channelScope || "All",
        valid_from: validFrom ? new Date(validFrom).toISOString() : undefined,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
        status: statusVal,
      });

      success("Fact Registered", `Fact '${title}' is now codified in the approved source of truth.`);
      setCreateModalOpen(false);
      resetCreateForm();
      fetchFacts();
    } catch (err: any) {
      error("Registration failed", err.message || "Could not register fact");
    } finally {
      setSaving(false);
    }
  };

  const resetCreateForm = () => {
    setTitle("");
    setCanonicalValue("");
    setDescription("");
    setSourceReference("");
    setProductScope("All");
    setRegionScope("Global");
    setChannelScope("All");
    setValidFrom("");
    setExpiresAt("");
    setStatusVal("Approved");
  };

  const handleArchiveFact = async (id: string, factTitle: string) => {
    if (!confirm(`Are you sure you want to archive fact '${factTitle}'? It will no longer match active content reviews.`)) return;
    try {
      await api.facts.archive(id);
      success("Fact Archived", `Fact '${factTitle}' has been safely archived.`);
      if (selectedFact?.id === id) {
        setSelectedFact(null);
      }
      fetchFacts();
    } catch (err: any) {
      error("Archive failed", err.message);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      warning("No file selected", "Please select a CSV file to import.");
      return;
    }

    setCsvUploading(true);
    try {
      const res = await api.facts.importCsv(csvFile);
      setCsvResult(res);
      if (res.imported_count > 0) {
        success("CSV Import Completed", `Successfully imported ${res.imported_count} facts.`);
        fetchFacts();
      } else {
        warning("Import Incomplete", "No facts were imported. Please check validation errors below.");
      }
    } catch (err: any) {
      error("CSV Import Failed", err.message || "Failed to process CSV file.");
    } finally {
      setCsvUploading(false);
    }
  };

  const downloadSampleCsv = () => {
    const csvContent =
      "title,canonical_value,source_reference,description,product_scope,region_scope,channel_scope,expires_at\n" +
      "Enterprise SLA,99.99% monthly uptime guarantee,Master Services Agreement §4.1,Core platform availability commitment,All,Global,All,2027-12-31\n" +
      "SOC-2 Type II Certified,Audited annually by independent CPA firm,AICPA SOC-2 Report 2026,Annual security and availability audit,All,North America,All,2027-06-30\n" +
      "EU Data Residency,Customer data stays encrypted in Frankfurt & Dublin,EU GDPR Compliance Charter §8,Strict European data residency,Northstar Pro,Europe,Web,2026-12-31\n";

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "brandproof_facts_sample.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedValue(true);
    setTimeout(() => setCopiedValue(false), 2000);
  };

  const canManageFacts =
    user?.role === "Fact Owner" ||
    user?.role === "Brand Manager" ||
    user?.role === "Admin";

  // Compute live breakdown counts
  const totalCount = facts.length;
  const approvedCount = facts.filter((f) => (f.effective_status || f.status) === "Approved" && !f.is_expired).length;
  const expiredCount = facts.filter((f) => f.is_expired || (f.effective_status || f.status) === "Expired").length;
  const expiringSoonCount = facts.filter(
    (f) =>
      !f.is_expired &&
      (f.effective_status || f.status) === "Approved" &&
      f.days_until_expiry !== null &&
      f.days_until_expiry !== undefined &&
      f.days_until_expiry <= 30 &&
      f.days_until_expiry >= 0
  ).length;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header & Stats Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Facts</h1>
            <p className="text-xs text-ink-soft mt-1">
              Approved statements with their source, scope and expiry date.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {canManageFacts && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setUploadModalOpen(true)}
                  className="bg-accent-soft/30 border-accent/40 text-accent-ink hover:bg-accent-soft text-xs"
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  <span>Upload Doc / Image</span>
                </Button>

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
                  <span>Register Fact</span>
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Fact Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-lg bg-surface border border-line flex items-center justify-between">
            <div>
              <div className="text-[11px] font-medium text-ink-soft">Total Registered</div>
              <div className="text-lg font-semibold text-ink mt-0.5">{totalCount}</div>
            </div>
            <div className="p-2 rounded-lg bg-accent-soft text-accent-ink border border-accent/20">
              <Database className="w-4 h-4" />
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-surface border border-line flex items-center justify-between">
            <div>
              <div className="text-[11px] font-medium text-ink-soft">Approved & Active</div>
              <div className="text-lg font-semibold text-emerald-400 mt-0.5">{approvedCount}</div>
            </div>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-surface border border-line flex items-center justify-between">
            <div>
              <div className="text-[11px] font-medium text-ink-soft">Expiring Soon (≤30d)</div>
              <div className="text-lg font-semibold text-amber-400 mt-0.5">{expiringSoonCount}</div>
            </div>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Clock className="w-4 h-4" />
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-surface border border-line flex items-center justify-between">
            <div>
              <div className="text-[11px] font-medium text-ink-soft">Expired & Excluded</div>
              <div className="text-lg font-semibold text-rose-400 mt-0.5">{expiredCount}</div>
            </div>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Search & Multi-Filter Bar */}
        <div className="space-y-3 p-3.5 rounded-lg bg-surface border border-line">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search facts by title, value, or source reference..."
                className="w-full bg-paper border border-line-strong rounded-lg pl-9 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => setExpiringOnly(!expiringOnly)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 ${
                  expiringOnly
                    ? "bg-amber-500/15 text-amber-300 border-amber-500/40"
                    : "bg-paper text-ink-soft border-line hover:text-ink"
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Expiring Soon</span>
              </button>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
              >
                <option value="All">All Statuses</option>
                <option value="Approved">Approved</option>
                <option value="Expired">Expired</option>
                <option value="Draft">Draft</option>
                <option value="Archived">Archived</option>
              </select>
            </div>
          </div>

          {/* Dimension Scopes Filters */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line text-xs">
            <span className="text-ink-mute text-[11px] flex items-center gap-1 mr-1">
              <Filter className="w-3 h-3" /> Scope Filters:
            </span>

            <select
              value={productFilter}
              onChange={(e) => setProductFilter(e.target.value)}
              className="bg-paper border border-line-strong rounded-md px-2 py-1 text-[11px] text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">Product: All</option>
              <option value="Northstar Cloud">Northstar Cloud</option>
              <option value="Northstar Pro">Northstar Pro</option>
              <option value="Northstar Sovereign">Northstar Sovereign</option>
            </select>

            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
              className="bg-paper border border-line-strong rounded-md px-2 py-1 text-[11px] text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">Region: All</option>
              <option value="Global">Global</option>
              <option value="North America">North America</option>
              <option value="Europe">Europe</option>
              <option value="APAC">APAC</option>
            </select>

            <select
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              className="bg-paper border border-line-strong rounded-md px-2 py-1 text-[11px] text-ink focus:outline-none focus:border-accent"
            >
              <option value="All">Channel: All</option>
              <option value="Web">Web</option>
              <option value="Social">Social</option>
              <option value="Email">Email</option>
              <option value="Sales Deck">Sales Deck</option>
              <option value="PR">PR</option>
            </select>

            {(productFilter !== "All" || regionFilter !== "All" || channelFilter !== "All" || statusFilter !== "All" || expiringOnly || search) && (
              <button
                onClick={() => {
                  setSearch("");
                  setStatusFilter("All");
                  setProductFilter("All");
                  setRegionFilter("All");
                  setChannelFilter("All");
                  setExpiringOnly(false);
                }}
                className="text-[11px] text-accent-ink hover:text-accent-ink ml-auto flex items-center gap-1"
              >
                <X className="w-3 h-3" /> Reset Filters
              </button>
            )}
          </div>
        </div>

        {/* Facts Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <Skeleton className="h-52 w-full" />
            <Skeleton className="h-52 w-full" />
            <Skeleton className="h-52 w-full" />
          </div>
        ) : facts.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {facts.map((fact) => {
              const expiryBadge = getFactExpiryBadge(fact);
              const isExpired = fact.is_expired || (fact.effective_status || fact.status) === "Expired";
              const isArchived = (fact.effective_status || fact.status) === "Archived";

              return (
                <div
                  key={fact.id}
                  onClick={() => setSelectedFact(fact)}
                  className={`p-4 rounded-lg bg-surface border transition-all cursor-pointer flex flex-col justify-between space-y-3 hover: ${
                    isExpired
                      ? "border-rose-500/40 hover:border-rose-500/70 bg-rose-950/10"
                      : isArchived
                      ? "border-line opacity-60 hover:opacity-100"
                      : "border-line hover:border-accent/50"
                  }`}
                >
                  <div className="space-y-2.5">
                    {/* Header Row */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Shield className={`w-4 h-4 shrink-0 mt-0.5 ${isExpired ? "text-rose-400" : "text-accent-ink"}`} />
                        <h3 className="font-semibold text-sm text-ink line-clamp-1">{fact.title}</h3>
                      </div>
                      <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${expiryBadge.colorClass}`}>
                        {expiryBadge.label}
                      </span>
                    </div>

                    {/* Canonical Value Callout */}
                    <div className="p-3 rounded-lg bg-paper border border-line text-xs text-ink font-medium leading-relaxed">
                      &ldquo;{fact.canonical_value}&rdquo;
                    </div>

                    {/* Scopes & Source */}
                    <div className="space-y-1.5 text-[11px]">
                      <div className="flex items-center justify-between text-ink-soft">
                        <span className="text-ink-mute">Source:</span>
                        <span className="font-mono text-emerald-400 text-right truncate max-w-[210px]">
                          {fact.source_reference}
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-ink-soft">
                        <span className="text-ink-mute">Scope:</span>
                        <span className="text-ink truncate max-w-[210px]">
                          {fact.product_scope} • {fact.region_scope} • {fact.channel_scope}
                        </span>
                      </div>

                      {fact.expires_at && (
                        <div className="flex items-center justify-between text-ink-soft">
                          <span className="text-ink-mute">Expires:</span>
                          <span className={isExpired ? "text-rose-400 font-mono" : "text-amber-400 font-mono"}>
                            {formatDate(fact.expires_at)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Card Footer */}
                  <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] text-ink-mute">
                    <span className="truncate max-w-[150px]">Owner: {fact.owner_name || "Fact Owner"}</span>
                    <span className="text-accent-ink hover:text-accent-ink font-medium">Inspect Fact →</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={<Database className="w-6 h-6" />}
            title="No approved facts found"
            description="No facts matched your active scope or status filters. Try clearing your filters or registering a new approved fact."
            action={
              canManageFacts ? (
                <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                  Register Approved Fact
                </Button>
              ) : undefined
            }
          />
        )}

        {/* Fact Detail Drawer */}
        {selectedFact && (
          <div className="fixed inset-0 z-50 overflow-hidden bg-ink/30 flex justify-end">
            <div
              className="w-full max-w-xl bg-surface border-l border-line h-full p-6 overflow-y-auto space-y-6 shadow-soft"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Drawer Header */}
              <div className="flex items-start justify-between border-b border-line pb-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-sunken text-ink-soft border border-line-strong">
                      ID: {selectedFact.id.slice(0, 8)}
                    </span>
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${
                        getFactExpiryBadge(selectedFact).colorClass
                      }`}
                    >
                      {getFactExpiryBadge(selectedFact).label}
                    </span>
                  </div>
                  <h2 className="text-lg font-semibold text-ink mt-1">{selectedFact.title}</h2>
                </div>
                <button
                  onClick={() => setSelectedFact(null)}
                  className="p-1 rounded-lg text-ink-soft hover:text-ink hover:bg-sunken"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Canonical Value Section */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink">
                    Canonical Value
                  </span>
                  <button
                    onClick={() => copyToClipboard(selectedFact.canonical_value)}
                    className="text-xs text-accent-ink hover:text-accent-ink flex items-center gap-1"
                  >
                    {copiedValue ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedValue ? "Copied" : "Copy Value"}</span>
                  </button>
                </div>
                <div className="p-4 rounded-lg bg-paper border border-line text-sm text-ink font-mono leading-relaxed">
                  {selectedFact.canonical_value}
                </div>
              </div>

              {/* Description */}
              {selectedFact.description && (
                <div className="space-y-1.5">
                  <span className="text-xs font-semibold text-ink">
                    Context & Description
                  </span>
                  <p className="text-xs text-ink leading-relaxed bg-paper p-3 rounded-lg border border-line">
                    {selectedFact.description}
                  </p>
                </div>
              )}

              {/* Source of Truth Verification */}
              <div className="space-y-2 p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                  <Shield className="w-4 h-4" />
                  <span>Verified Source Reference (Traceable)</span>
                </div>
                <div className="text-xs text-ink font-mono break-all">
                  {selectedFact.source_reference}
                </div>
              </div>

              {/* Multi-Dimensional Scope Matrix */}
              <div className="space-y-3">
                <span className="text-xs font-semibold text-ink">
                  Scope Matrix
                </span>
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <div className="text-[11px] text-ink-mute flex items-center gap-1">
                      <Layers className="w-3 h-3 text-accent-ink" /> Product Scope
                    </div>
                    <div className="text-xs font-medium text-ink mt-1 truncate">
                      {selectedFact.product_scope}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <div className="text-[11px] text-ink-mute flex items-center gap-1">
                      <Globe className="w-3 h-3 text-emerald-400" /> Region Scope
                    </div>
                    <div className="text-xs font-medium text-ink mt-1 truncate">
                      {selectedFact.region_scope}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <div className="text-[11px] text-ink-mute flex items-center gap-1">
                      <Tag className="w-3 h-3 text-amber-400" /> Channel Scope
                    </div>
                    <div className="text-xs font-medium text-ink mt-1 truncate">
                      {selectedFact.channel_scope}
                    </div>
                  </div>
                </div>
              </div>

              {/* Lifecycle & Expiry */}
              <div className="space-y-2 p-3.5 rounded-lg bg-paper border border-line text-xs">
                <span className="text-xs font-semibold text-ink">
                  Validity Lifecycle
                </span>
                <div className="grid grid-cols-2 gap-3 pt-2 text-[11px]">
                  <div>
                    <span className="text-ink-mute">Valid From:</span>
                    <div className="text-ink font-mono mt-0.5">
                      {selectedFact.valid_from ? formatDate(selectedFact.valid_from) : "Immediate / Creation"}
                    </div>
                  </div>
                  <div>
                    <span className="text-ink-mute">Expires At:</span>
                    <div className="text-ink font-mono mt-0.5">
                      {selectedFact.expires_at ? formatDate(selectedFact.expires_at) : "No Expiration (Permanent)"}
                    </div>
                  </div>
                </div>

                {selectedFact.is_expired && (
                  <div className="mt-2 p-2.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 flex items-center gap-2 text-[11px]">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>This fact has expired and is automatically excluded from active publication approvals.</span>
                  </div>
                )}
              </div>

              {/* Ownership & Metadata */}
              <div className="space-y-1 text-[11px] text-ink-mute pt-2 border-t border-line">
                <div className="flex justify-between">
                  <span>Fact Owner:</span>
                  <span className="text-ink">{selectedFact.owner_name || "Designated Fact Owner"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Registered:</span>
                  <span className="text-ink-soft">{formatDate(selectedFact.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Last Updated:</span>
                  <span className="text-ink-soft">{formatDate(selectedFact.updated_at)}</span>
                </div>
              </div>

              {/* Drawer Actions */}
              <div className="pt-4 border-t border-line flex items-center justify-between gap-3">
                {canManageFacts && selectedFact.status !== "Archived" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleArchiveFact(selectedFact.id, selectedFact.title)}
                    className="border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                  >
                    <Archive className="w-3.5 h-3.5 mr-1.5" />
                    <span>Archive Fact</span>
                  </Button>
                )}

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedFact(null)}
                  className="ml-auto bg-sunken text-ink border-line-strong"
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Register Fact Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
            <div className="bg-surface border border-line rounded-xl w-full max-w-lg p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div>
                  <h2 className="text-base font-semibold text-ink">Register Approved Fact</h2>
                  <p className="text-xs text-ink-soft mt-0.5">
                    Codify a verified truth that claims must trace back to.
                  </p>
                </div>
                <button
                  onClick={() => setCreateModalOpen(false)}
                  className="p-1 rounded-lg text-ink-soft hover:text-ink"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateFact} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Fact Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. SOC-2 Type II Certification"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Canonical Value * (The exact approved statement)
                  </label>
                  <textarea
                    required
                    rows={2}
                    value={canonicalValue}
                    onChange={(e) => setCanonicalValue(e.target.value)}
                    placeholder="e.g. Audited annually by independent CPA firm with zero non-conformities."
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Source Reference * (Traceable evidence link or document)
                  </label>
                  <input
                    type="text"
                    required
                    value={sourceReference}
                    onChange={(e) => setSourceReference(e.target.value)}
                    placeholder="e.g. AICPA SOC-2 Report 2026 §3.2"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    Description / Context (Optional)
                  </label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="e.g. Covers all core infrastructure and database services."
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>

                {/* Scope Triplet */}
                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">
                      Product Scope
                    </label>
                    <input
                      type="text"
                      value={productScope}
                      onChange={(e) => setProductScope(e.target.value)}
                      placeholder="All"
                      className="w-full bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">
                      Region Scope
                    </label>
                    <input
                      type="text"
                      value={regionScope}
                      onChange={(e) => setRegionScope(e.target.value)}
                      placeholder="Global"
                      className="w-full bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">
                      Channel Scope
                    </label>
                    <input
                      type="text"
                      value={channelScope}
                      onChange={(e) => setChannelScope(e.target.value)}
                      placeholder="All"
                      className="w-full bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>

                {/* Dates & Expiration */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">
                      Valid From (Optional)
                    </label>
                    <input
                      type="date"
                      value={validFrom}
                      onChange={(e) => setValidFrom(e.target.value)}
                      className="w-full bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-ink-soft mb-1">
                      Expires At (Optional)
                    </label>
                    <input
                      type="date"
                      value={expiresAt}
                      onChange={(e) => setExpiresAt(e.target.value)}
                      className="w-full bg-paper border border-line-strong rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2.5 pt-3 border-t border-line">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setCreateModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={saving}>
                    {saving ? "Registering..." : "Codify Fact"}
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
                  <h2 className="text-base font-semibold text-ink">Bulk Import Facts via CSV</h2>
                </div>
                <button
                  onClick={() => setCsvModalOpen(false)}
                  className="p-1 rounded-lg text-ink-soft hover:text-ink"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="p-3.5 rounded-lg bg-paper border border-line space-y-2 text-xs">
                <div className="font-semibold text-ink">Expected CSV Header Format:</div>
                <code className="block p-2 rounded bg-surface text-[11px] text-emerald-400 font-mono break-all border border-line">
                  title,canonical_value,source_reference,description,product_scope,region_scope,channel_scope,expires_at
                </code>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11px] text-ink-soft">Required: title, canonical_value, source_reference</span>
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

                {/* Import Result / Error Box */}
                {csvResult && (
                  <div
                    className={`p-3.5 rounded-lg text-xs space-y-2 border ${
                      csvResult.imported_count > 0
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                        : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                    }`}
                  >
                    <div className="font-semibold flex items-center justify-between">
                      <span>Imported: {csvResult.imported_count} facts</span>
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setCsvModalOpen(false)}
                  >
                    Close
                  </Button>
                  <Button type="submit" size="sm" disabled={csvUploading || !csvFile}>
                    {csvUploading ? "Uploading..." : "Import Facts"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Method B: Document or Image Upload Modal */}
        <KnowledgeUploadModal
          isOpen={uploadModalOpen}
          onClose={() => setUploadModalOpen(false)}
          targetCategory="fact"
          onItemCreated={fetchFacts}
        />
      </div>
    </AppShell>
  );
}
