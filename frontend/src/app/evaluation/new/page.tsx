"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ShieldCheck,
  ArrowLeft,
  ArrowRight,
  FileText,
  Upload,
  Sliders,
  CheckCircle2,
  AlertCircle,
  BookOpen,
  Sparkles,
  Info,
  Scale,
  Hash,
  X,
  Play,
  Globe,
  Building,
  Target,
  FileCheck2,
  RefreshCw,
  RotateCcw,
  Clock,
  Layers,
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
const DRAFT_STORAGE_KEY = "brandproof_evaluation_draft_v1";

const SAMPLE_COPY = `# Apex Cloud Enterprise Q3 Announcement

Apex Cloud delivers 99.99% verified uptime across all enterprise availability zones.

Our ISO 27001 certified architecture reduces cloud deployment overhead by 45% compared to legacy infrastructure.

Guaranteed deployment within 15 minutes with automated compliance guardrails active from day one.`;

interface DraftState {
  title: string;
  brandWebsite: string;
  industry: string;
  product: string;
  region: string;
  channel: string;
  contentType: string;
  intendedAudience: string;
  purpose: string;
  supportingEvidence: string;
  pastedText: string;
  inputMode: "paste" | "upload";
  savedAt: number;
}

export default function NewEvaluationPage() {
  const router = useRouter();
  const { success, error, warning, info } = useToast();

  // Wizard Step State: 1 | 2 | 3
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);

  // Step 1: Campaign Details & Context
  const [title, setTitle] = useState("Apex Cloud Enterprise Q3 Launch");
  const [brandWebsite, setBrandWebsite] = useState("https://apexcloud.io");
  const [industry, setIndustry] = useState("Cloud Infrastructure & SaaS");
  const [product, setProduct] = useState("Northstar Pro");
  const [region, setRegion] = useState("India");
  const [channel, setChannel] = useState("Advertisement");
  const [contentType, setContentType] = useState("Ad Copy");
  const [intendedAudience, setIntendedAudience] = useState("Enterprise IT & Security Decision Makers");
  const [purpose, setPurpose] = useState("Promote verified uptime, ISO 27001 compliance, and deployment efficiency");

  // Step 2: Content & Supporting Evidence
  const [inputMode, setInputMode] = useState<"paste" | "upload">("paste");
  const [pastedText, setPastedText] = useState(SAMPLE_COPY);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);
  const [supportingEvidence, setSupportingEvidence] = useState("Doc Ref #ISO-27001-CERT, Uptime SLA Report 2026");

  // Step 3: Knowledge Scoping & Submission
  const [applicableKnowledge, setApplicableKnowledge] = useState<ApplicableKnowledgeResponse | null>(null);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submissionStage, setSubmissionStage] = useState<
    "idle" | "ingesting" | "extracting" | "voice_check" | "citation_gate" | "scoring" | "completed"
  >("idle");

  // Draft Management State
  const [hasRestoredDraft, setHasRestoredDraft] = useState(false);
  const [hasExistingDraft, setHasExistingDraft] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<number | null>(null);

  // Check for saved draft on initial load
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (raw) {
        const parsed: DraftState = JSON.parse(raw);
        if (parsed && parsed.title) {
          setHasExistingDraft(true);
          setDraftSavedAt(parsed.savedAt);
        }
      }
    } catch (e) {
      // Ignore localStorage errors
    }
  }, []);

  // Autosave to localStorage on field changes
  useEffect(() => {
    // Only save after initial mount
    const timeout = setTimeout(() => {
      try {
        const draft: DraftState = {
          title,
          brandWebsite,
          industry,
          product,
          region,
          channel,
          contentType,
          intendedAudience,
          purpose,
          supportingEvidence,
          pastedText,
          inputMode,
          savedAt: Date.now(),
        };
        localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
        setDraftSavedAt(draft.savedAt);
      } catch (e) {
        // Ignore quota errors
      }
    }, 800);

    return () => clearTimeout(timeout);
  }, [
    title,
    brandWebsite,
    industry,
    product,
    region,
    channel,
    contentType,
    intendedAudience,
    purpose,
    supportingEvidence,
    pastedText,
    inputMode,
  ]);

  const handleRestoreDraft = () => {
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (raw) {
        const d: DraftState = JSON.parse(raw);
        if (d.title) setTitle(d.title);
        if (d.brandWebsite) setBrandWebsite(d.brandWebsite);
        if (d.industry) setIndustry(d.industry);
        if (d.product) setProduct(d.product);
        if (d.region) setRegion(d.region);
        if (d.channel) setChannel(d.channel);
        if (d.contentType) setContentType(d.contentType);
        if (d.intendedAudience) setIntendedAudience(d.intendedAudience);
        if (d.purpose) setPurpose(d.purpose);
        if (d.supportingEvidence) setSupportingEvidence(d.supportingEvidence);
        if (d.pastedText) setPastedText(d.pastedText);
        if (d.inputMode) setInputMode(d.inputMode);

        setHasRestoredDraft(true);
        setHasExistingDraft(false);
        info("Draft Restored", "Your autosaved evaluation inputs have been loaded.");
      }
    } catch (e) {
      error("Restore Failed", "Could not restore the saved draft.");
    }
  };

  const handleDiscardDraft = () => {
    try {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
      setHasExistingDraft(false);
      setHasRestoredDraft(false);
      info("Draft Discarded", "The autosaved draft has been cleared.");
    } catch (e) {
      // Ignore
    }
  };

  // Fetch live applicable knowledge scoped to current selection
  const fetchScopedKnowledge = useCallback(async () => {
    setLoadingKnowledge(true);
    try {
      const res = await api.knowledge.getApplicable({
        product: product === "All Products" ? undefined : product,
        region: region === "Global" ? undefined : region,
        channel: channel === "All" ? undefined : channel,
      });
      setApplicableKnowledge(res);
    } catch (err) {
      console.warn("Could not preview scoped knowledge:", err);
    } finally {
      setLoadingKnowledge(false);
    }
  }, [product, region, channel]);

  useEffect(() => {
    if (currentStep === 3) {
      fetchScopedKnowledge();
    }
  }, [currentStep, fetchScopedKnowledge]);

  // File drag & drop validation
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

  // Step Navigation Handlers
  const handleNextToStep2 = () => {
    if (!title.trim()) {
      warning("Evaluation Title Required", "Please specify a campaign or evaluation name.");
      return;
    }
    setCurrentStep(2);
  };

  const handleNextToStep3 = () => {
    if (inputMode === "upload") {
      if (!file) {
        warning("File Required", "Please select a file to upload or switch to pasted text.");
        return;
      }
      if (fileValidationError) {
        warning("Invalid File", fileValidationError);
        return;
      }
    } else {
      if (!pastedText.trim()) {
        warning("Content Required", "Please paste marketing or advertisement copy to evaluate.");
        return;
      }
    }
    setCurrentStep(3);
  };

  // Submit Evaluation with Simulated / Real-time Pipeline Progress
  const handleSubmitEvaluation = async () => {
    if (submitting) return;

    if (!title.trim()) {
      warning("Evaluation Title Required", "Please specify a campaign or evaluation name.");
      setCurrentStep(1);
      return;
    }

    setSubmitting(true);
    setSubmissionStage("ingesting");

    // Stage simulation timers for rich feedback during pipeline execution
    const t1 = setTimeout(() => setSubmissionStage("extracting"), 500);
    const t2 = setTimeout(() => setSubmissionStage("voice_check"), 1100);
    const t3 = setTimeout(() => setSubmissionStage("citation_gate"), 1700);
    const t4 = setTimeout(() => setSubmissionStage("scoring"), 2300);

    try {
      const formData = new FormData();
      formData.append("title", title.trim());
      formData.append("product", product.trim() || "All");
      formData.append("region", region.trim() || "Global");
      formData.append("channel", channel.trim() || "All");
      formData.append("content_type", contentType.trim() || "General Marketing");
      formData.append("intended_audience", intendedAudience.trim() || "All Audiences");
      formData.append("purpose", purpose.trim());

      const evidencePayload = [
        brandWebsite.trim() ? `Brand Website: ${brandWebsite.trim()}` : "",
        industry.trim() ? `Industry: ${industry.trim()}` : "",
        supportingEvidence.trim() ? `Supporting Evidence: ${supportingEvidence.trim()}` : "",
      ]
        .filter(Boolean)
        .join(" | ");

      if (evidencePayload) {
        formData.append("supporting_evidence", evidencePayload);
      }

      if (inputMode === "upload" && file) {
        formData.append("file", file);
      } else {
        formData.append("pasted_text", pastedText.trim());
      }

      const evalDetail = await api.evaluation.submitNew(formData);

      // Clear draft on successful submission
      try {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
      } catch (e) {
        // Ignore
      }

      setSubmissionStage("completed");
      success(
        "Evaluation Completed",
        `Brand governance scan completed for "${title}". Evaluation ID: ${evalDetail.id}`
      );
      router.push(`/reviews/${evalDetail.id}`);
    } catch (err: any) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      console.error("Evaluation submission error:", err);
      error("Evaluation Failed", err.message || "Failed to process content and run evaluation.");
      setSubmitting(false);
      setSubmissionStage("idle");
    }
  };

  const wordsCount = pastedText.trim() ? pastedText.trim().split(/\s+/).length : 0;
  const charsCount = pastedText.length;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6 pb-12">
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
            Multi-step governance audit: configure campaign context, ingest content, and run claim verification through CitationGate.
          </p>
        </div>

        {/* Autosave Draft Notification Banner */}
        {hasExistingDraft && !hasRestoredDraft && (
          <div className="p-3.5 rounded-lg bg-accent-soft/40 border border-accent/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-ink">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-accent-ink shrink-0" />
              <span>
                You have an autosaved evaluation draft{" "}
                {draftSavedAt ? `from ${new Date(draftSavedAt).toLocaleTimeString()}` : ""}.
              </span>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              <Button
                size="sm"
                variant="outline"
                onClick={handleDiscardDraft}
                className="text-xs border-line-strong text-ink hover:bg-sunken h-7"
              >
                Discard
              </Button>
              <Button
                size="sm"
                onClick={handleRestoreDraft}
                className="text-xs bg-accent hover:bg-accent-hover text-ink font-semibold h-7"
              >
                <RotateCcw className="w-3 h-3 mr-1" />
                Resume Draft
              </Button>
            </div>
          </div>
        )}

        {/* Wizard Step Navigation Bar */}
        <div className="p-3 rounded-xl bg-surface border border-line">
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setCurrentStep(1)}
              className={`flex items-center gap-2.5 p-2 rounded-lg text-left transition-all ${
                currentStep === 1
                  ? "bg-paper border border-accent/40 shadow-sm"
                  : "hover:bg-sunken text-ink-soft"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  currentStep === 1
                    ? "bg-accent text-ink"
                    : currentStep > 1
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-sunken text-ink-mute"
                }`}
              >
                {currentStep > 1 ? "✓" : "1"}
              </div>
              <div className="overflow-hidden">
                <span className="block text-xs font-semibold text-ink truncate">1. Context & Scopes</span>
                <span className="block text-[10px] text-ink-mute truncate">Brand, URL & Criteria</span>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleNextToStep2()}
              className={`flex items-center gap-2.5 p-2 rounded-lg text-left transition-all ${
                currentStep === 2
                  ? "bg-paper border border-accent/40 shadow-sm"
                  : "hover:bg-sunken text-ink-soft"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  currentStep === 2
                    ? "bg-accent text-ink"
                    : currentStep > 2
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-sunken text-ink-mute"
                }`}
              >
                {currentStep > 2 ? "✓" : "2"}
              </div>
              <div className="overflow-hidden">
                <span className="block text-xs font-semibold text-ink truncate">2. Content Ingestion</span>
                <span className="block text-[10px] text-ink-mute truncate">Copy & Evidence Files</span>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleNextToStep3()}
              className={`flex items-center gap-2.5 p-2 rounded-lg text-left transition-all ${
                currentStep === 3
                  ? "bg-paper border border-accent/40 shadow-sm"
                  : "hover:bg-sunken text-ink-soft"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  currentStep === 3
                    ? "bg-accent text-ink"
                    : "bg-sunken text-ink-mute"
                }`}
              >
                3
              </div>
              <div className="overflow-hidden">
                <span className="block text-xs font-semibold text-ink truncate">3. Review & Launch</span>
                <span className="block text-[10px] text-ink-mute truncate">Scope check & Scan</span>
              </div>
            </button>
          </div>
        </div>

        {/* STEP 1: CAMPAIGN DETAILS & CONTEXT */}
        {currentStep === 1 && (
          <div className="space-y-6 animate-in fade-in">
            <Card>
              <CardHeader className="pb-3 border-b border-line">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold text-ink flex items-center gap-2">
                      <Sliders className="w-4 h-4 text-accent-ink" />
                      <span>Step 1: Campaign Identity & Governed Scopes</span>
                    </CardTitle>
                    <CardDescription className="text-xs text-ink-soft mt-0.5">
                      Define the campaign name, website URL, industry vertical, and context scopes to activate matching brand knowledge.
                    </CardDescription>
                  </div>
                  <Badge variant="outline" className="text-[11px] font-mono text-accent-ink border-accent/30 bg-accent-soft">
                    Context Scoping
                  </Badge>
                </div>
              </CardHeader>

              <div className="p-6 space-y-4">
                {/* Title */}
                <div>
                  <label className="block text-xs font-semibold text-ink">
                    Evaluation / Campaign Name <span className="text-rose-400">*</span>
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

                {/* Website URL & Industry */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                  <div>
                    <label className="block text-xs font-medium text-ink flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-accent-ink" />
                      Brand Website / URL
                    </label>
                    <input
                      type="url"
                      value={brandWebsite}
                      onChange={(e) => setBrandWebsite(e.target.value)}
                      placeholder="https://yourbrand.com"
                      className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-ink flex items-center gap-1.5">
                      <Building className="w-3.5 h-3.5 text-accent-ink" />
                      Industry / Vertical
                    </label>
                    <select
                      value={industry}
                      onChange={(e) => setIndustry(e.target.value)}
                      className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="Cloud Infrastructure & SaaS">Cloud Infrastructure & SaaS</option>
                      <option value="Financial Services & Fintech">Financial Services & Fintech</option>
                      <option value="Healthcare & Life Sciences">Healthcare & Life Sciences</option>
                      <option value="E-Commerce & Retail">E-Commerce & Retail</option>
                      <option value="Cybersecurity & Defense">Cybersecurity & Defense</option>
                      <option value="Manufacturing & Industrial">Manufacturing & Industrial</option>
                      <option value="Consumer Technology">Consumer Technology</option>
                    </select>
                  </div>
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

                {/* Content Category & Intended Audience */}
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

                {/* Goals & Objective */}
                <div className="pt-1">
                  <label className="block text-xs font-medium text-ink flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-accent-ink" />
                    Campaign Goals & Compliance Criteria
                  </label>
                  <input
                    type="text"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="e.g. Highlight 99.99% SLA and ISO 27001 accreditation without unverified superlatives"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>
              </div>
            </Card>

            <div className="flex items-center justify-between pt-2">
              <Link href="/evaluation">
                <Button type="button" variant="outline" className="text-xs border-line-strong text-ink">
                  <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Evaluations
                </Button>
              </Link>

              <Button
                type="button"
                onClick={handleNextToStep2}
                className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs px-5 py-2"
              >
                Proceed to Content Ingestion
                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </div>
          </div>
        )}

        {/* STEP 2: CONTENT & SUPPORTING EVIDENCE INGESTION */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in">
            <Card>
              <CardHeader className="pb-3 border-b border-line">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm font-semibold text-ink flex items-center gap-2">
                      <FileText className="w-4 h-4 text-accent-ink" />
                      <span>Step 2: Marketing Copy & Evidence Documents</span>
                    </CardTitle>
                    <CardDescription className="text-xs text-ink-soft mt-0.5">
                      Provide the content payload for claim extraction and reference any supporting audit evidence.
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
                      Paste Copy
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

              <div className="p-6 space-y-5">
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
                          className="text-accent-ink hover:underline text-xs flex items-center gap-1 font-medium"
                        >
                          <Sparkles className="w-3 h-3" /> Load Sample Copy
                        </button>
                      </div>
                    </div>

                    <textarea
                      rows={10}
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

                {/* Supporting Evidence Citation Input */}
                <div className="pt-2 border-t border-line">
                  <label className="block text-xs font-medium text-ink flex items-center gap-1.5">
                    <FileCheck2 className="w-3.5 h-3.5 text-accent-ink" />
                    Supporting Evidence Reference / Documentation Citation
                  </label>
                  <p className="text-[11px] text-ink-mute mt-0.5">
                    Optionally cite official reports, certifications, or internal specs that validate numerical claims.
                  </p>
                  <input
                    type="text"
                    value={supportingEvidence}
                    onChange={(e) => setSupportingEvidence(e.target.value)}
                    placeholder="e.g. Doc Ref #ISO-27001-CERT, SOC2 Type II Audit § 4.1"
                    className="mt-1.5 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                </div>
              </div>
            </Card>

            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentStep(1)}
                className="text-xs border-line-strong text-ink"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Scopes
              </Button>

              <Button
                type="button"
                onClick={handleNextToStep3}
                className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs px-5 py-2"
              >
                Review & Confirm Launch
                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </div>
          </div>
        )}

        {/* STEP 3: REVIEW & LAUNCH */}
        {currentStep === 3 && (
          <div className="space-y-6 animate-in fade-in">
            {/* Confirmation Summary Card */}
            <Card>
              <CardHeader className="pb-3 border-b border-line">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold text-ink flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Step 3: Review Submission & Scoped Knowledge</span>
                    </CardTitle>
                    <CardDescription className="text-xs text-ink-soft mt-0.5">
                      Verify campaign parameters and active canonical knowledge before launching the governance audit.
                    </CardDescription>
                  </div>
                  <Badge variant="outline" className="text-[11px] font-mono text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                    Ready to Scan
                  </Badge>
                </div>
              </CardHeader>

              <div className="p-6 space-y-6">
                {/* Campaign Summary Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <span className="text-[11px] text-ink-mute block">Evaluation Title</span>
                    <span className="font-semibold text-ink truncate block mt-0.5">{title}</span>
                  </div>

                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <span className="text-[11px] text-ink-mute block">Brand / Product</span>
                    <span className="font-semibold text-accent-ink truncate block mt-0.5">{product}</span>
                  </div>

                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <span className="text-[11px] text-ink-mute block">Region & Channel</span>
                    <span className="font-semibold text-ink truncate block mt-0.5">
                      {region} • {channel}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-paper border border-line">
                    <span className="text-[11px] text-ink-mute block">Content Payload</span>
                    <span className="font-semibold text-emerald-400 truncate block mt-0.5">
                      {inputMode === "upload" ? file?.name || "Uploaded File" : `${wordsCount} words`}
                    </span>
                  </div>
                </div>

                {/* Strategic Intent & URL */}
                <div className="p-3 rounded-lg bg-paper border border-line text-xs space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-ink-mute font-medium w-28 shrink-0">Website URL:</span>
                    <span className="text-ink font-mono">{brandWebsite || "Not specified"}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-ink-mute font-medium w-28 shrink-0">Industry:</span>
                    <span className="text-ink">{industry}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-ink-mute font-medium w-28 shrink-0">Strategic Goals:</span>
                    <span className="text-ink">{purpose || "Standard compliance audit"}</span>
                  </div>
                  {supportingEvidence && (
                    <div className="flex items-center gap-2">
                      <span className="text-ink-mute font-medium w-28 shrink-0">Evidence Citations:</span>
                      <span className="text-ink font-mono text-[11px]">{supportingEvidence}</span>
                    </div>
                  )}
                </div>

                {/* Content Payload Preview */}
                <div>
                  <div className="flex items-center justify-between pb-1.5">
                    <span className="text-xs font-semibold text-ink">Payload Content Preview</span>
                    <button
                      type="button"
                      onClick={() => setCurrentStep(2)}
                      className="text-xs text-accent-ink hover:underline"
                    >
                      Edit Content
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-sunken border border-line text-xs font-mono text-ink-soft max-h-36 overflow-y-auto leading-relaxed">
                    {inputMode === "upload"
                      ? `File attached: ${file?.name} (${((file?.size || 0) / 1024).toFixed(1)} KB)`
                      : pastedText}
                  </div>
                </div>

                {/* Live Scoped Knowledge Scope */}
                <div className="p-4 rounded-lg bg-surface border border-line space-y-3 text-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-line">
                    <span className="font-semibold text-ink flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-accent-ink" />
                      Live Scoped Knowledge Activation
                    </span>
                    <span className="text-[11px] text-ink-mute font-mono">
                      {product} • {region} • {channel}
                    </span>
                  </div>

                  {loadingKnowledge ? (
                    <div className="grid grid-cols-4 gap-2">
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                  ) : applicableKnowledge ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="p-2.5 rounded bg-paper border border-line">
                        <span className="text-[10px] text-ink-mute block uppercase">Canonical Facts</span>
                        <span className="text-sm font-semibold text-emerald-400">
                          {applicableKnowledge.counts.facts} active
                        </span>
                      </div>
                      <div className="p-2.5 rounded bg-paper border border-line">
                        <span className="text-[10px] text-ink-mute block uppercase">Governance Rules</span>
                        <span className="text-sm font-semibold text-accent-ink">
                          {applicableKnowledge.counts.rules} active
                        </span>
                      </div>
                      <div className="p-2.5 rounded bg-paper border border-line">
                        <span className="text-[10px] text-ink-mute block uppercase">Nomenclature Terms</span>
                        <span className="text-sm font-semibold text-ink">
                          {applicableKnowledge.counts.terms} defined
                        </span>
                      </div>
                      <div className="p-2.5 rounded bg-paper border border-line">
                        <span className="text-[10px] text-ink-mute block uppercase">Voice Guidelines</span>
                        <span className="text-sm font-semibold text-ink">
                          {applicableKnowledge.counts.guidelines} active
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[11px] text-ink-mute">Knowledge scoping engine online.</p>
                  )}
                </div>

                {/* CitationGate Policy Invariant */}
                <div className="p-3.5 rounded-lg bg-surface border border-line flex items-center gap-3 text-xs text-ink-soft">
                  <ShieldCheck className="w-5 h-5 text-accent-ink shrink-0" />
                  <span>
                    <strong>CitationGate Guarantee:</strong> Every factual claim extracted from this copy will be strictly verified against your organization&apos;s active knowledge records. Contradictions trigger Blocker findings.
                  </span>
                </div>
              </div>
            </Card>

            {/* Stepper Progress Feedback during submission */}
            {submitting && (
              <Card className="p-6 border-accent bg-accent-soft/20 animate-in fade-in">
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-ink flex items-center gap-2">
                      <RefreshCw className="w-4 h-4 text-accent-ink animate-spin" />
                      Executing Brand Governance Pipeline...
                    </span>
                    <span className="font-mono text-accent-ink font-semibold">
                      {submissionStage === "ingesting" && "20% — Ingesting"}
                      {submissionStage === "extracting" && "40% — Extracting Claims"}
                      {submissionStage === "voice_check" && "60% — Checking Voice & Rules"}
                      {submissionStage === "citation_gate" && "80% — CitationGate Verification"}
                      {submissionStage === "scoring" && "95% — Scoring & Telemetry"}
                      {submissionStage === "completed" && "100% — Finalized"}
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-sunken rounded-full h-2 overflow-hidden border border-line">
                    <div
                      className="bg-accent h-2 transition-all duration-500 rounded-full"
                      style={{
                        width:
                          submissionStage === "ingesting"
                            ? "20%"
                            : submissionStage === "extracting"
                            ? "40%"
                            : submissionStage === "voice_check"
                            ? "60%"
                            : submissionStage === "citation_gate"
                            ? "80%"
                            : submissionStage === "scoring"
                            ? "95%"
                            : "100%",
                      }}
                    />
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[11px] text-ink-soft pt-1">
                    <div className={submissionStage !== "idle" ? "text-emerald-400 font-semibold" : ""}>
                      ✓ 1. Ingestion
                    </div>
                    <div
                      className={
                        submissionStage === "extracting" ||
                        submissionStage === "voice_check" ||
                        submissionStage === "citation_gate" ||
                        submissionStage === "scoring" ||
                        submissionStage === "completed"
                          ? "text-emerald-400 font-semibold"
                          : ""
                      }
                    >
                      ✓ 2. Claim Ledger
                    </div>
                    <div
                      className={
                        submissionStage === "voice_check" ||
                        submissionStage === "citation_gate" ||
                        submissionStage === "scoring" ||
                        submissionStage === "completed"
                          ? "text-emerald-400 font-semibold"
                          : ""
                      }
                    >
                      ✓ 3. Voice & Rules
                    </div>
                    <div
                      className={
                        submissionStage === "citation_gate" ||
                        submissionStage === "scoring" ||
                        submissionStage === "completed"
                          ? "text-emerald-400 font-semibold"
                          : ""
                      }
                    >
                      ✓ 4. CitationGate
                    </div>
                    <div
                      className={
                        submissionStage === "scoring" || submissionStage === "completed"
                          ? "text-emerald-400 font-semibold"
                          : ""
                      }
                    >
                      ✓ 5. Risk Scoring
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {/* Launch Action Footer */}
            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                disabled={submitting}
                onClick={() => setCurrentStep(2)}
                className="text-xs border-line-strong text-ink"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Content
              </Button>

              <Button
                type="button"
                disabled={submitting}
                onClick={handleSubmitEvaluation}
                className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs px-6 py-2.5 shadow-md"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin mr-2" />
                    Running Governance Audit...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    Confirm & Launch Evaluation
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
