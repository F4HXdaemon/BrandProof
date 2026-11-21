"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ShieldCheck,
  ArrowLeft,
  FileText,
  Upload,
  Sliders,
  CheckCircle2,
  AlertCircle,
  FileCode,
  BookOpen,
  Sparkles,
  Info,
  Scale,
  Hash,
  X,
  Play,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { ApplicableKnowledgeResponse } from "@/lib/types";

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15MB
const ALLOWED_EXTENSIONS = [".txt", ".text", ".docx", ".pdf", ".md", ".markdown"];

const SAMPLE_COPY = `# Apex Cloud Enterprise Q3 Announcement

Apex Cloud delivers 99.99% verified uptime across all enterprise availability zones.

Our ISO 27001 certified architecture reduces cloud deployment overhead by 45% compared to legacy infrastructure.

Guaranteed deployment within 15 minutes with automated compliance guardrails active from day one.`;

export default function NewEvaluationPage() {
  const router = useRouter();
  const { success, error, warning } = useToast();

  // Mode: Paste or Upload
  const [inputMode, setInputMode] = useState<"paste" | "upload">("paste");
  const [pastedText, setPastedText] = useState(SAMPLE_COPY);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);

  // Form Fields
  const [title, setTitle] = useState("Apex Cloud Enterprise Q3 Launch");
  const [product, setProduct] = useState("Northstar Pro");
  const [region, setRegion] = useState("India");
  const [channel, setChannel] = useState("Advertisement");
  const [contentType, setContentType] = useState("Ad Copy");
  const [intendedAudience, setIntendedAudience] = useState("Enterprise IT & Security Decision Makers");
  const [purpose, setPurpose] = useState("Promote verified uptime and deployment efficiency");
  const [supportingEvidence, setSupportingEvidence] = useState("");

  // Scoping & Submitting States
  const [applicableKnowledge, setApplicableKnowledge] = useState<ApplicableKnowledgeResponse | null>(null);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Fetch live applicable knowledge whenever scopes change
  useEffect(() => {
    let isCurrent = true;
    const fetchScopedKnowledge = async () => {
      setLoadingKnowledge(true);
      try {
        const res = await api.knowledge.getApplicable({
          product: product === "All Products" ? undefined : product,
          region: region === "Global" ? undefined : region,
          channel: channel === "All" ? undefined : channel,
        });
        if (isCurrent) {
          setApplicableKnowledge(res);
        }
      } catch (err) {
        console.warn("Could not preview scoped knowledge:", err);
      } finally {
        if (isCurrent) setLoadingKnowledge(false);
      }
    };

    fetchScopedKnowledge();
    return () => {
      isCurrent = false;
    };
  }, [product, region, channel]);

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    setFileValidationError(null);
    const ext = "." + (selectedFile.name.split(".").pop()?.toLowerCase() || "");
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setFileValidationError(
        `Unsupported file type '${ext}'. Please upload TXT, DOCX, PDF, or MD.`
      );
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      setFileValidationError(
        `File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds 15 MB limit.`
      );
      return;
    }

    setFile(selectedFile);
    if (!title || title === "Apex Cloud Enterprise Q3 Launch") {
      setTitle(selectedFile.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      warning("Evaluation Title Required", "Please specify a campaign or evaluation name.");
      return;
    }

    if (inputMode === "upload") {
      if (!file) {
        warning("File Required", "Please select a file to upload or switch to pasted text.");
        return;
      }
    } else {
      if (!pastedText.trim()) {
        warning("Content Required", "Please paste marketing or advertisement copy to evaluate.");
        return;
      }
    }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("title", title.trim());
      formData.append("product", product.trim() || "All");
      formData.append("region", region.trim() || "Global");
      formData.append("channel", channel.trim() || "All");
      formData.append("content_type", contentType.trim() || "General Marketing");
      formData.append("intended_audience", intendedAudience.trim() || "All Audiences");
      formData.append("purpose", purpose.trim());
      if (supportingEvidence.trim()) {
        formData.append("supporting_evidence", supportingEvidence.trim());
      }

      if (inputMode === "upload" && file) {
        formData.append("file", file);
      } else {
        formData.append("pasted_text", pastedText.trim());
      }

      const evalDetail = await api.evaluation.submitNew(formData);
      success(
        "Evaluation Completed",
        `Brand governance and CitationGate scan completed for "${title}". Evaluation ID: ${evalDetail.id}`
      );
      router.push(`/reviews/${evalDetail.id}`);
    } catch (err: any) {
      console.error("Evaluation submission error:", err);
      error("Evaluation Failed", err.message || "Failed to process content and run evaluation.");
      setSubmitting(false);
    }
  };

  const wordsCount = pastedText.trim() ? pastedText.trim().split(/\s+/).length : 0;
  const charsCount = pastedText.length;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Navigation Breadcrumb & Header */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link
              href="/evaluation"
              className="text-xs text-ink-soft hover:text-ink transition-colors inline-flex items-center gap-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Evaluation Hub</span>
            </Link>
            <span className="text-ink-mute">/</span>
            <span className="text-xs text-accent-ink font-medium">New Evaluation</span>
          </div>
          <h1 className="page-title text-3xl text-ink">New Brand Evaluation</h1>
          <p className="text-xs text-ink-soft">
            Submit marketing or advertisement copy to run claim extraction, CitationGate source verification, and risk scoring.
          </p>
        </div>

        {/* Informative Guidance Banner */}
        <div className="p-4 rounded-lg bg-surface border border-line flex items-start gap-3 text-xs text-ink-soft">
          <div className="w-7 h-7 rounded-lg bg-accent-soft text-accent-ink flex items-center justify-center shrink-0 border border-accent/20">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-ink">
              CitationGate Governance Policy: &ldquo;No valid source = No finding&rdquo;
            </p>
            <p className="text-ink-soft leading-relaxed">
              Every factual claim in your marketing content is automatically extracted and analyzed against approved canonical facts.
              Findings are only raised when backed by an active, scoped knowledge record. Missing, expired, or out-of-scope evidence is flagged distinctly.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Section 1: Campaign & Scoping Context */}
          <Card>
            <CardHeader className="pb-3 border-b border-line">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold text-ink flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-accent-ink" />
                    <span>Evaluation Scopes & Intent Context</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-ink-soft mt-0.5">
                    Define the campaign name, target audience, and product scope to activate matching brand rules.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-[11px] font-mono text-accent-ink border-accent/30 bg-accent-soft">
                  Contextual Scoping
                </Badge>
              </div>
            </CardHeader>

            <div className="p-6 space-y-4">
              {/* Title */}
              <div>
                <label className="block text-xs font-semibold text-ink">
                  Campaign / Evaluation Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Apex Cloud Q3 Multi-Region Advertisement"
                  className="mt-1.5 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                />
              </div>

              {/* Scopes Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
                <div>
                  <label className="block text-xs font-medium text-ink">Product Scope</label>
                  <select
                    value={product}
                    onChange={(e) => setProduct(e.target.value)}
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="Northstar Pro">Northstar Pro</option>
                    <option value="Northstar Sovereign Cloud">Northstar Sovereign Cloud</option>
                    <option value="CloudShield Intelligence">CloudShield Intelligence</option>
                    <option value="All Products">All Products</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink">Target Region</label>
                  <select
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="India">India</option>
                    <option value="Global">Global</option>
                    <option value="North America">North America</option>
                    <option value="European Union">European Union</option>
                    <option value="Asia Pacific">Asia Pacific</option>
                    <option value="UK">UK</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink">Distribution Channel</label>
                  <select
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="Advertisement">Advertisement</option>
                    <option value="Website & Landing Page">Website & Landing Page</option>
                    <option value="Social Media">Social Media</option>
                    <option value="Email Campaign">Email Campaign</option>
                    <option value="Press Release">Press Release</option>
                    <option value="Sales Collateral">Sales Collateral</option>
                    <option value="Whitepaper">Technical Whitepaper</option>
                  </select>
                </div>
              </div>

              {/* Content Type & Audience */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div>
                  <label className="block text-xs font-medium text-ink">Content Category</label>
                  <select
                    value={contentType}
                    onChange={(e) => setContentType(e.target.value)}
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                  >
                    <option value="Ad Copy">Ad Copy</option>
                    <option value="Landing Page Copy">Landing Page Copy</option>
                    <option value="Social Media Post">Social Media Post</option>
                    <option value="Email Campaign">Email Campaign</option>
                    <option value="Press Announcement">Press Announcement</option>
                    <option value="Product Packaging">Product Packaging</option>
                    <option value="Whitepaper / Research">Whitepaper / Research</option>
                    <option value="General Marketing">General Marketing</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink">Intended Audience</label>
                  <input
                    type="text"
                    value={intendedAudience}
                    onChange={(e) => setIntendedAudience(e.target.value)}
                    placeholder="e.g. Enterprise IT leaders, Procurement Teams"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>
              </div>

              {/* Purpose & Supporting Evidence */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div>
                  <label className="block text-xs font-medium text-ink">Campaign Objective / Purpose</label>
                  <input
                    type="text"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="e.g. Highlight 99.99% SLA and ISO 27001 accreditation"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink">
                    Supporting Evidence Reference <span className="text-ink-mute font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    value={supportingEvidence}
                    onChange={(e) => setSupportingEvidence(e.target.value)}
                    placeholder="e.g. Doc Ref #ISO-2026-CERT, SOC2 Report v3.1"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>
              </div>
            </div>
          </Card>

          {/* Section 2: Marketing Content Input */}
          <Card>
            <CardHeader className="pb-3 border-b border-line">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <CardTitle className="text-sm font-semibold text-ink flex items-center gap-2">
                    <FileText className="w-4 h-4 text-accent-ink" />
                    <span>Marketing Content & Advertisement Text</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-ink-soft mt-0.5">
                    Paste your advertisement text directly or upload an asset file (.txt, .docx, .pdf, .md).
                  </CardDescription>
                </div>

                {/* Input Mode Switcher */}
                <div className="flex items-center gap-1 p-1 rounded-lg bg-paper border border-line self-start">
                  <button
                    type="button"
                    onClick={() => setInputMode("paste")}
                    className={`text-xs px-3 py-1 rounded font-medium transition-colors ${
                      inputMode === "paste"
                        ? "bg-accent text-ink shadow-sm"
                        : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    Paste Text
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode("upload")}
                    className={`text-xs px-3 py-1 rounded font-medium transition-colors ${
                      inputMode === "upload"
                        ? "bg-accent text-ink shadow-sm"
                        : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    Upload File
                  </button>
                </div>
              </div>
            </CardHeader>

            <div className="p-6">
              {inputMode === "paste" ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-ink-mute">
                    <span>Markdown formatting supported</span>
                    <div className="flex items-center gap-3">
                      <span>{wordsCount} words</span>
                      <span>{charsCount} characters</span>
                      <button
                        type="button"
                        onClick={() => setPastedText(SAMPLE_COPY)}
                        className="text-accent-ink hover:underline text-xs flex items-center gap-1"
                      >
                        <Sparkles className="w-3 h-3" /> Load Sample
                      </button>
                    </div>
                  </div>

                  <textarea
                    rows={9}
                    required={inputMode === "paste"}
                    value={pastedText}
                    onChange={(e) => setPastedText(e.target.value)}
                    placeholder="Enter or paste marketing copy, headline, body text, or ad claims here..."
                    className="w-full bg-paper border border-line-strong rounded-lg p-3 text-xs text-ink font-mono placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent leading-relaxed"
                  />
                </div>
              ) : (
                <div className="space-y-4">
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                      dragActive
                        ? "border-accent bg-accent-soft"
                        : "border-line-strong bg-paper hover:bg-sunken"
                    }`}
                  >
                    <input
                      id="eval-file-upload"
                      type="file"
                      accept=".txt,.text,.docx,.pdf,.md,.markdown"
                      onChange={handleFileChange}
                      className="hidden"
                    />

                    {file ? (
                      <div className="space-y-3">
                        <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-400 mx-auto flex items-center justify-center border border-emerald-500/20">
                          <CheckCircle2 className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-ink">{file.name}</p>
                          <p className="text-xs text-ink-mute">
                            {(file.size / 1024).toFixed(1)} KB • Ready for extraction
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setFile(null)}
                          className="text-xs border-line-strong text-ink-soft hover:text-ink"
                        >
                          <X className="w-3.5 h-3.5 mr-1" /> Remove File
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="w-12 h-12 rounded-full bg-sunken mx-auto flex items-center justify-center text-ink-soft border border-line">
                          <Upload className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-ink">
                            Drag & drop marketing asset here, or{" "}
                            <label
                              htmlFor="eval-file-upload"
                              className="text-accent-ink hover:underline cursor-pointer"
                            >
                              browse files
                            </label>
                          </p>
                          <p className="text-[11px] text-ink-mute mt-1">
                            Supported: TXT, DOCX, PDF, Markdown (up to 15 MB)
                          </p>
                        </div>
                      </div>
                    )}
                  </div>

                  {fileValidationError && (
                    <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                      <span>{fileValidationError}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Section 3: Live Scope Knowledge Preview */}
          <div className="p-4 rounded-lg bg-surface border border-line space-y-2 text-xs">
            <div className="flex items-center justify-between pb-1.5 border-b border-line">
              <span className="font-semibold text-ink flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5 text-accent-ink" />
                Live Scoped Knowledge Base
              </span>
              <span className="text-[11px] text-ink-mute font-mono">
                {product} • {region} • {channel}
              </span>
            </div>

            {loadingKnowledge ? (
              <div className="grid grid-cols-4 gap-2 pt-1">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : applicableKnowledge ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                <div className="p-2 rounded bg-paper border border-line">
                  <span className="text-[10px] text-ink-mute block uppercase">Active Facts</span>
                  <span className="text-xs font-semibold text-emerald-400">
                    {applicableKnowledge.counts.facts} facts
                  </span>
                </div>
                <div className="p-2 rounded bg-paper border border-line">
                  <span className="text-[10px] text-ink-mute block uppercase">Active Rules</span>
                  <span className="text-xs font-semibold text-accent-ink">
                    {applicableKnowledge.counts.rules} rules
                  </span>
                </div>
                <div className="p-2 rounded bg-paper border border-line">
                  <span className="text-[10px] text-ink-mute block uppercase">Brand Terms</span>
                  <span className="text-xs font-semibold text-ink">
                    {applicableKnowledge.counts.terms} terms
                  </span>
                </div>
                <div className="p-2 rounded bg-paper border border-line">
                  <span className="text-[10px] text-ink-mute block uppercase">Voice Guidelines</span>
                  <span className="text-xs font-semibold text-ink">
                    {applicableKnowledge.counts.guidelines} guidelines
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-ink-mute pt-1">Scoping engine connected.</p>
            )}
          </div>

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2">
            <Link href="/evaluation">
              <Button type="button" variant="outline" className="text-xs border-line-strong text-ink">
                <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Evaluations
              </Button>
            </Link>

            <Button
              type="submit"
              disabled={submitting}
              className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs px-5 py-2"
            >
              {submitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                  Running CitationGate Scan...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  Start Brand Evaluation
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
