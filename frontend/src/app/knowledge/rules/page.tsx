"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Scale,
  Plus,
  Trash2,
  Shield,
  Settings2,
  Code2,
  Archive,
  Filter,
  CheckCircle2,
  Search,
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
import { Rule, RuleType, SeverityLevel } from "@/lib/types";

const RULE_TYPES: RuleType[] = [
  "TERM_CHECK",
  "REQUIRED_DISCLAIMER",
  "FORBIDDEN_PHRASE",
  "EXACT_VALUE",
  "EXPIRY_CHECK",
  "REGEX",
  "ACCESSIBILITY",
  "CUSTOM",
];

const SEVERITIES: SeverityLevel[] = ["Blocker", "High", "Warning", "Info"];

export default function RulesPage() {
  const { user } = useAuth();
  const { success, error } = useToast();

  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("All");
  const [severityFilter, setSeverityFilter] = useState<string>("All");
  const [search, setSearch] = useState("");

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ruleType, setRuleType] = useState<RuleType>("TERM_CHECK");
  const [severity, setSeverity] = useState<SeverityLevel>("Blocker");
  const [sourceReference, setSourceReference] = useState("");
  const [configJson, setConfigJson] = useState('{\n  "trigger_keywords": ["beta"],\n  "required_text": "Preview only"\n}');
  const [productScope, setProductScope] = useState("All");
  const [regionScope, setRegionScope] = useState("Global");
  const [channelScope, setChannelScope] = useState("All");
  const [saving, setSaving] = useState(false);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.rules.list({
        rule_type: typeFilter === "All" ? undefined : typeFilter,
        severity: severityFilter === "All" ? undefined : severityFilter,
      });
      setRules(res);
    } catch (err: any) {
      error("Failed to load rules", err.message);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, severityFilter, error]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !description) {
      error("Missing fields", "Name and description are required.");
      return;
    }

    let parsedConfig: Record<string, any> = {};
    try {
      parsedConfig = JSON.parse(configJson);
    } catch (err) {
      error("Invalid JSON Configuration", "Please check your configuration JSON syntax.");
      return;
    }

    setSaving(true);
    try {
      await api.rules.create({
        name,
        description,
        rule_type: ruleType,
        severity,
        source_reference: sourceReference || "Governance Standards §4.0",
        configuration: parsedConfig,
        product_scope: productScope || "All",
        region_scope: regionScope || "Global",
        channel_scope: channelScope || "All",
        status: "Approved",
        active: true,
      });

      success("Rule Created", `Governance rule '${name}' registered.`);
      setCreateModalOpen(false);
      resetForm();
      fetchRules();
    } catch (err: any) {
      error("Creation failed", err.message);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setName("");
    setDescription("");
    setRuleType("TERM_CHECK");
    setSeverity("Blocker");
    setSourceReference("");
    setConfigJson('{\n  "trigger_keywords": ["beta"],\n  "required_text": "Preview only"\n}');
    setProductScope("All");
    setRegionScope("Global");
    setChannelScope("All");
  };

  const handleArchive = async (id: string, ruleName: string) => {
    if (!confirm(`Are you sure you want to archive rule '${ruleName}'?`)) return;
    try {
      await api.rules.archive(id);
      success("Rule Archived", `Archived '${ruleName}'.`);
      fetchRules();
    } catch (err: any) {
      error("Archive failed", err.message);
    }
  };

  const canManage = user?.role === "Brand Manager" || user?.role === "Admin";

  const filteredRules = rules.filter((r) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.name.toLowerCase().includes(q) ||
      r.description.toLowerCase().includes(q) ||
      (r.source_reference && r.source_reference.toLowerCase().includes(q))
    );
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Rules</h1>
            <p className="text-xs text-ink-soft mt-1">
              The checks the review engine runs: terms, disclaimers and exact values.
            </p>
          </div>

          <div>
            {canManage && (
              <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                <Plus className="w-4 h-4 mr-1.5" />
                <span>Add Rule</span>
              </Button>
            )}
          </div>
        </div>

        {/* Filter Bar */}
        <div className="p-3.5 rounded-lg bg-surface border border-line space-y-3">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search rules by name, description, or source..."
                className="w-full bg-paper border border-line-strong rounded-lg pl-9 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
              />
            </div>

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
            <button
              onClick={() => setTypeFilter("All")}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                typeFilter === "All"
                  ? "bg-accent text-ink font-semibold"
                  : "bg-paper text-ink-soft hover:text-ink border border-line"
              }`}
            >
              All Types
            </button>
            {RULE_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                  typeFilter === t
                    ? "bg-accent text-ink font-semibold"
                    : "bg-paper text-ink-soft hover:text-ink border border-line"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Rules Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton className="h-56 w-full" />
            <Skeleton className="h-56 w-full" />
          </div>
        ) : filteredRules.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredRules.map((rule) => {
              const ruleConfig = rule.configuration || rule.config || {};
              return (
                <Card
                  key={rule.id}
                  className={`p-4 bg-surface border transition-colors flex flex-col justify-between space-y-3 ${
                    rule.status === "Archived" ? "opacity-60 border-line" : "border-line hover:border-line-strong"
                  }`}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20">
                          {rule.rule_type}
                        </span>
                        <h3 className="font-semibold text-sm text-ink">{rule.name}</h3>
                      </div>
                      <Badge variant="severity" value={rule.severity} />
                    </div>

                    <p className="text-xs text-ink leading-relaxed">
                      {rule.description}
                    </p>

                    {/* JSON Config viewer */}
                    <div className="space-y-1">
                      <span className="text-[11px] font-mono text-ink-mute flex items-center gap-1">
                        <Code2 className="w-3 h-3 text-accent-ink" /> Config Specification:
                      </span>
                      <pre className="p-2.5 rounded-lg bg-paper border border-line text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-32">
                        {JSON.stringify(ruleConfig, null, 2)}
                      </pre>
                    </div>

                    {/* Evidence & Scope */}
                    <div className="space-y-1 text-[11px] text-ink-soft pt-1">
                      {rule.source_reference && (
                        <div className="flex items-center justify-between">
                          <span className="text-ink-mute flex items-center gap-1">
                            <Shield className="w-3 h-3 text-emerald-400" /> Source:
                          </span>
                          <span className="font-mono text-emerald-400 truncate max-w-[220px]">
                            {rule.source_reference}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-ink-mute">Scope:</span>
                        <span className="text-ink">
                          {rule.product_scope || "All"} • {rule.region_scope || "Global"} • {rule.channel_scope || "All"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-line flex items-center justify-between text-[11px] text-ink-mute">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Status: {rule.status || "Approved"}
                    </span>
                    {canManage && rule.status !== "Archived" && (
                      <button
                        onClick={() => handleArchive(rule.id, rule.name)}
                        className="text-ink-mute hover:text-rose-400 flex items-center gap-1 transition-colors"
                      >
                        <Archive className="w-3.5 h-3.5" />
                        <span>Archive</span>
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={<Scale className="w-6 h-6" />}
            title="No rules found"
            description="No rules match your type or severity filters."
            action={
              canManage ? (
                <Button size="sm" onClick={() => setCreateModalOpen(true)}>
                  Add Rule
                </Button>
              ) : undefined
            }
          />
        )}

        {/* Create Rule Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
            <div className="bg-surface border border-line rounded-xl w-full max-w-xl p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h2 className="text-base font-semibold text-ink">Add Governance Rule</h2>
                <button onClick={() => setCreateModalOpen(false)} className="text-ink-soft hover:text-ink">✕</button>
              </div>

              <form onSubmit={handleCreate} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Rule Name *</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Beta Feature SLA Disclaimer Rule"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">Description *</label>
                  <input
                    type="text"
                    required
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="e.g. Enforces mandatory experimental disclaimer whenever 'beta' or 'preview' is mentioned."
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink mb-1">Rule Type</label>
                    <select
                      value={ruleType}
                      onChange={(e) => setRuleType(e.target.value as RuleType)}
                      className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent font-mono"
                    >
                      {RULE_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
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
                    placeholder="e.g. Legal Compliance Charter §4.2"
                    className="w-full bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink mb-1">
                    JSON Configuration (Deterministic rule parameters)
                  </label>
                  <textarea
                    rows={4}
                    value={configJson}
                    onChange={(e) => setConfigJson(e.target.value)}
                    className="w-full bg-paper border border-line-strong rounded-lg p-2.5 text-xs font-mono text-emerald-400 focus:outline-none focus:border-accent"
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
                    {saving ? "Registering..." : "Save Rule"}
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
