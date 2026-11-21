"use client";

import React, { useEffect, useState, useCallback } from "react";
import { BookMarked, Plus, Filter, Trash2, Archive, Shield, Layers, Globe, Tag, CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { Guideline, SeverityLevel } from "@/lib/types";

const CATEGORIES = [
  "All",
  "Brand Voice",
  "Claims",
  "Legal",
  "Product",
  "Accessibility",
  "Visual",
  "Regional",
];

const SEVERITIES: SeverityLevel[] = ["Blocker", "High", "Warning", "Info"];

export default function GuidelinesPage() {
  const { user } = useAuth();
  const { success, error } = useToast();

  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>("All");
  const [severityFilter, setSeverityFilter] = useState<string>("All");
  const [search, setSearch] = useState("");

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("Claims");
  const [severity, setSeverity] = useState<SeverityLevel>("Blocker");
  const [sourceReference, setSourceReference] = useState("");
  const [productScope, setProductScope] = useState("All");
  const [regionScope, setRegionScope] = useState("Global");
  const [channelScope, setChannelScope] = useState("All");
  const [saving, setSaving] = useState(false);

  const fetchGuidelines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.guidelines.list({
        category: categoryFilter === "All" ? undefined : categoryFilter,
        severity: severityFilter === "All" ? undefined : severityFilter,
      });
      setGuidelines(res);
    } catch (err: any) {
      error("Failed to load guidelines", err.message);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, severityFilter, error]);

  useEffect(() => {
    fetchGuidelines();
  }, [fetchGuidelines]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !description) {
      error("Missing fields", "Title and description are required.");
      return;
    }
    setSaving(true);
    try {
      await api.guidelines.create({
        title,
        description,
        category,
        severity,
        source_reference: sourceReference || "Brand Compliance Standards §1.0",
        product_scope: productScope || "All",
        region_scope: regionScope || "Global",
        channel_scope: channelScope || "All",
        status: "Approved",
        active: true,
      });
      success("Guideline Registered", `Guideline '${title}' added.`);
      setCreateModalOpen(false);
      resetForm();
      fetchGuidelines();
    } catch (err: any) {
      error("Creation failed", err.message);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setCategory("Claims");
    setSeverity("Blocker");
    setSourceReference("");
    setProductScope("All");
    setRegionScope("Global");
    setChannelScope("All");
  };

  const handleArchive = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to archive guideline '${name}'?`)) return;
    try {
      await api.guidelines.archive(id);
      success("Guideline Archived", `Archived '${name}'.`);
      fetchGuidelines();
    } catch (err: any) {
      error("Archive failed", err.message);
    }
  };

  const canManage = user?.role === "Brand Manager" || user?.role === "Admin";

  const filteredGuidelines = guidelines.filter((g) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      g.title.toLowerCase().includes(q) ||
      g.description.toLowerCase().includes(q) ||
      (g.source_reference && g.source_reference.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Guidelines</h1>
            <p className="text-xs text-ink-soft mt-1">
              Guidance on claims, legal, voice, product, accessibility and regional rules.
            </p>
          </div>

          <div>
            {canManage && (
              <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                <Plus className="w-4 h-4 mr-1.5" />
                <span>Add Guideline</span>
              </Button>
            )}
          </div>
        </div>

        {/* Filter Bar */}
        <div className="p-3.5 rounded-lg bg-surface border border-line space-y-3">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter guidelines by keywords..."
              className="w-full sm:flex-1 bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
            />

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
              >
                <option value="All">All Severities</option>
                <option value="Blocker">Blocker</option>
                <option value="High">High</option>
                <option value="Warning">Warning</option>
                <option value="Info">Info</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 pt-2 border-t border-line">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  categoryFilter === cat
                    ? "bg-accent text-ink font-semibold"
                    : "bg-paper text-ink-soft hover:text-ink border border-line"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
        ) : filteredGuidelines.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredGuidelines.map((guideline) => (
              <Card
                key={guideline.id}
                className={`p-4 bg-surface border transition-colors flex flex-col justify-between space-y-3 ${
                  guideline.status === "Archived" ? "opacity-60 border-line" : "border-line hover:border-line-strong"
                }`}
              >
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <span className="text-[11px] font-mono text-accent-ink bg-accent-soft px-2 py-0.5 rounded border border-accent/20">
                        {guideline.category}
                      </span>
                      <h3 className="font-semibold text-sm text-ink">{guideline.title}</h3>
                    </div>
                    <Badge variant="severity" value={guideline.severity} />
                  </div>

                  <p className="text-xs text-ink leading-relaxed bg-paper p-3 rounded-lg border border-line">
                    {guideline.description}
                  </p>

                  <div className="space-y-1 text-[11px] text-ink-soft">
                    {guideline.source_reference && (
                      <div className="flex items-center justify-between">
                        <span className="text-ink-mute flex items-center gap-1">
                          <Shield className="w-3 h-3 text-emerald-400" /> Evidence Source:
                        </span>
                        <span className="font-mono text-emerald-400 truncate max-w-[240px]">
                          {guideline.source_reference}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span className="text-ink-mute">Scope:</span>
                      <span className="text-ink">
                        {guideline.product_scope} • {guideline.region_scope} • {guideline.channel_scope}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] text-ink-mute">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span>Status: {guideline.status || (guideline.active ? "Approved" : "Archived")}</span>
                  </span>
                  {canManage && guideline.status !== "Archived" && (
                    <button
                      onClick={() => handleArchive(guideline.id, guideline.title)}
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
            icon={<BookMarked className="w-6 h-6" />}
            title="No guidelines found"
            description="No guidelines match your category and severity filters."
            action={
              canManage ? (
                <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                  Add Guideline
                </Button>
              ) : undefined
            }
          />
        )}

        {/* Create Guideline Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
            <div className="bg-surface border border-line rounded-xl w-full max-w-lg p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h2 className="text-base font-semibold text-ink">Add Brand Guideline</h2>
                <button onClick={() => setCreateModalOpen(false)} className="text-ink-soft hover:text-ink">✕</button>
              </div>

              <form onSubmit={handleCreate} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Guideline Title *</label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Unsubstantiated Competitive Superiority Claims"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Description & Governance Rule *</label>
                  <textarea
                    required
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="e.g. Do not claim '#1' or 'fastest cloud' without referencing third-party benchmark."
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink mb-1">Category</label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      {CATEGORIES.filter((c) => c !== "All").map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-ink mb-1">Severity</label>
                    <select
                      value={severity}
                      onChange={(e) => setSeverity(e.target.value as SeverityLevel)}
                      className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      {SEVERITIES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Evidence Source Reference</label>
                  <input
                    type="text"
                    value={sourceReference}
                    onChange={(e) => setSourceReference(e.target.value)}
                    placeholder="e.g. Legal Compliance Charter §3.1"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent font-mono"
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
                    {saving ? "Saving..." : "Save Guideline"}
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
