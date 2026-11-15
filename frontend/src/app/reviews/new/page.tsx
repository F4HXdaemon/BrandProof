"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Upload,
  FileText,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Info,
  CheckCircle2,
  FileUp,
  Sliders,
  AlertCircle,
  FileCode,
  BookOpen,
  Scale,
  Hash,
  X,
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

export default function NewReviewPage() {
  const router = useRouter();
  const { success, error, warning } = useToast();

  // Wizard Step (1: Content, 2: Context / Intent Card, 3: Confirmation)
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);

  // Step 1: Content
  const [inputMode, setInputMode] = useState<"paste" | "upload">("paste");
  const [pastedText, setPastedText] = useState(
    `# Northstar Pro Launch Draft\n\nNorthstar Premium cuts employee onboarding time by 60%.\n\nOur ISO 27001 certified platform is the #1 onboarding solution and guarantees immediate productivity improvements across enterprise workflows.\n\nAutomated setup takes under 15 minutes with zero manual intervention required.`
  );
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);

  // Step 2: Context / Intent Card
  const [title, setTitle] = useState("Northstar Pro Q2 Launch Draft");
  const [product, setProduct] = useState("Northstar Pro");
  const [region, setRegion] = useState("India");
  const [channel, setChannel] = useState("Advertisement");
  const [contentType, setContentType] = useState("Ad Copy");
  const [intendedAudience, setIntendedAudience] = useState("Enterprise IT leaders");
  const [purpose, setPurpose] = useState("Promote faster employee onboarding");

  // Step 3: Confirmation & Live Scoping
  const [applicableKnowledge, setApplicableKnowledge] = useState<ApplicableKnowledgeResponse | null>(null);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [submitting, setSubmitting] = useState(false);

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
    if (!title || title === "Northstar Pro Q2 Launch Draft") {
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

  // Fetch live applicable knowledge when transitioning to Step 3
  const fetchApplicableKnowledge = async () => {
    setLoadingKnowledge(true);
    try {
      const data = await api.knowledge.getApplicable({
        product: product.trim() || undefined,
        region: region.trim() || undefined,
        channel: channel.trim() || undefined,
      });
      setApplicableKnowledge(data);
    } catch (err) {
      console.error("Failed to load applicable knowledge:", err);
    } finally {
      setLoadingKnowledge(false);
    }
  };

  useEffect(() => {
    if (currentStep === 3) {
      fetchApplicableKnowledge();
    }
  }, [currentStep, product, region, channel]);

  // Validation before going to next step
  const handleProceedToStep2 = () => {
    if (inputMode === "upload") {
      if (!file) {
        warning("Document Required", "Please select or drop a valid document (TXT, DOCX, PDF, MD).");
        return;
      }
      if (fileValidationError) {
        warning("Invalid Document", fileValidationError);
        return;
      }
    } else {
      if (!pastedText.trim()) {
        warning("Content Required", "Please enter or paste your marketing copy or document text.");
        return;
      }
    }
    setCurrentStep(2);
  };

  const handleProceedToStep3 = () => {
    if (!title.trim()) {
      warning("Title Required", "Please provide a descriptive title for this review.");
      return;
    }
    setCurrentStep(3);
  };

  // Submit Review
  const handleSubmitReview = async () => {
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

      if (inputMode === "upload" && file) {
        formData.append("file", file);
      } else {
        formData.append("pasted_text", pastedText.trim());
      }

      const reviewDetail = await api.reviews.submitNew(formData);
      success(
        "Review Initialized",
        `Document ingested and brand governance scan initiated for "${title}".`
      );
      router.push(`/reviews/${reviewDetail.id}`);
    } catch (err: any) {
      error("Ingestion Failed", err.message || "Failed to process document and initiate review.");
      setSubmitting(false);
    }
  };

  // Quick word & character count for pasted text
  const wordsCount = pastedText.trim() ? pastedText.trim().split(/\s+/).length : 0;
  const charsCount = pastedText.length;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Link
                href="/reviews"
                className="text-xs text-ink-soft hover:text-ink transition-colors inline-flex items-center gap-1"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Reviews</span>
              </Link>
              <span className="text-ink-mute">/</span>
              <span className="text-xs text-accent-ink font-medium">New Review</span>
            </div>
            <h1 className="page-title text-3xl text-ink">
              New review
            </h1>
            <p className="text-xs text-ink-soft mt-1">
              Add a draft to check it against approved facts and guidelines.
            </p>
          </div>
        </div>

        {/* Multi-step progress stepper */}
        <div className="grid grid-cols-3 gap-2">
          <div
            className={`p-3 rounded-lg border transition-all ${
              currentStep === 1
                ? "bg-accent-soft border-accent/50 text-accent-ink"
                : currentStep > 1
                ? "bg-surface border-emerald-500/30 text-emerald-400"
                : "bg-surface border-line text-ink-mute"
            }`}
          >
            <div className="flex items-center gap-2 text-xs font-semibold">
              <span className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-semibold bg-sunken border border-line-strong">
                {currentStep > 1 ? "✓" : "1"}
              </span>
              <span>Step 1: Content Ingestion</span>
            </div>
            <p className="text-[11px] text-ink-soft mt-1 pl-7">
              {inputMode === "upload" && file ? file.name : "TXT, DOCX, PDF, or Paste"}
            </p>
          </div>

          <div
            className={`p-3 rounded-lg border transition-all ${
              currentStep === 2
                ? "bg-accent-soft border-accent/50 text-accent-ink"
                : currentStep > 2
                ? "bg-surface border-emerald-500/30 text-emerald-400"
                : "bg-surface border-line text-ink-mute"
            }`}
          >
            <div className="flex items-center gap-2 text-xs font-semibold">
              <span className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-semibold bg-sunken border border-line-strong">
                {currentStep > 2 ? "✓" : "2"}
              </span>
              <span>Step 2: Intent Card</span>
            </div>
            <p className="text-[11px] text-ink-soft mt-1 pl-7">
              {product} • {region} • {channel}
            </p>
          </div>

          <div
            className={`p-3 rounded-lg border transition-all ${
              currentStep === 3
                ? "bg-accent-soft border-accent/50 text-accent-ink"
                : "bg-surface border-line text-ink-mute"
            }`}
          >
            <div className="flex items-center gap-2 text-xs font-semibold">
              <span className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-semibold bg-sunken border border-line-strong">
                3
              </span>
              <span>Step 3: Confirm & Launch</span>
            </div>
            <p className="text-[11px] text-ink-soft mt-1 pl-7">Live Knowledge Scoping</p>
          </div>
        </div>

        {/* STEP 1: CONTENT */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Submit Content Draft</CardTitle>
                  <CardDescription>
                    Provide content via direct text paste or upload an existing document
                  </CardDescription>
                </div>
                {/* Mode Selector Tabs */}
                <div className="flex items-center bg-paper border border-line rounded-lg p-1">
                  <button
                    type="button"
                    onClick={() => setInputMode("paste")}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
                      inputMode === "paste"
                        ? "bg-accent text-ink "
                        : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Paste Content</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode("upload")}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
                      inputMode === "upload"
                        ? "bg-accent text-ink "
                        : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Upload Document</span>
                  </button>
                </div>
              </CardHeader>

              {inputMode === "paste" ? (
                <div className="space-y-3">
                  <textarea
                    rows={12}
                    value={pastedText}
                    onChange={(e) => setPastedText(e.target.value)}
                    placeholder="Paste draft copy, press release, ad claims, or whitepaper markdown here..."
                    className="w-full bg-paper border border-line-strong rounded-lg p-3.5 text-xs text-ink font-mono placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent leading-relaxed"
                  />
                  <div className="flex items-center justify-between text-[11px] text-ink-mute font-mono px-1">
                    <span>
                      {wordsCount} words • {charsCount} characters
                    </span>
                    <span>Supports Markdown formatting (# headings, bullet points, quotes)</span>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Drag and Drop Zone */}
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                      dragActive
                        ? "border-accent bg-accent-soft"
                        : "border-line hover:border-line-strong bg-paper"
                    }`}
                  >
                    <input
                      type="file"
                      id="file-upload-input"
                      onChange={handleFileChange}
                      accept=".txt,.docx,.pdf,.md"
                      className="hidden"
                    />

                    <div className="flex flex-col items-center justify-center space-y-3">
                      <div className="w-12 h-12 rounded-full bg-accent-soft border border-accent/80 flex items-center justify-center text-accent-ink">
                        <FileUp className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">
                          Drag and drop your document here, or{" "}
                          <label
                            htmlFor="file-upload-input"
                            className="text-accent-ink hover:text-accent-ink cursor-pointer underline font-semibold"
                          >
                            browse files
                          </label>
                        </p>
                        <p className="text-xs text-ink-mute mt-1">
                          Supported formats: <strong>TXT, DOCX, PDF, MD</strong> (Max 15 MB)
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* File Selection Status Card */}
                  {file && (
                    <div className="p-3.5 rounded-lg bg-accent-soft border border-accent/30 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded bg-accent-soft border border-accent/30 flex items-center justify-center text-accent-ink">
                          <FileCode className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-ink">
                              {file.name}
                            </span>
                            <Badge variant="status" value="Approved">
                              Ready
                            </Badge>
                          </div>
                          <p className="text-[11px] text-ink-soft">
                            Type: {file.type || file.name.split(".").pop()?.toUpperCase()} • Size:{" "}
                            {(file.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFile(null)}
                        className="p-1.5 rounded-lg hover:bg-sunken text-ink-soft hover:text-rose-400 transition-colors"
                        title="Remove file"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {fileValidationError && (
                    <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/60 text-xs text-rose-300 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                      <span>{fileValidationError}</span>
                    </div>
                  )}

                  {/* Architecture note for Image OCR */}
                  <div className="p-3 rounded-lg bg-paper border border-line text-[11px] text-ink-soft flex items-center gap-2">
                    <Info className="w-4 h-4 text-accent-ink shrink-0" />
                    <span>
                      <strong>Visual OCR Preparation:</strong> Multi-modal image banner parsing is architected for later integration. Current pipeline decomposes TXT, DOCX, and PDF into structured semantic chunks.
                    </span>
                  </div>
                </div>
              )}
            </Card>

            <div className="flex items-center justify-end">
              <Button type="button" onClick={handleProceedToStep2}>
                Proceed to Intent Card <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* STEP 2: CONTEXT / INTENT CARD */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Step 2 — Context / Intent Card</CardTitle>
                  <CardDescription>
                    Contextual scoping parameters ensure relevant brand rules and facts are evaluated
                  </CardDescription>
                </div>
                <div className="p-1.5 rounded-lg bg-paper border border-line text-xs text-accent-ink flex items-center gap-1.5 font-mono">
                  <Sliders className="w-3.5 h-3.5" />
                  <span>Scoped Governance</span>
                </div>
              </CardHeader>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-ink">
                    Review Title <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Northstar Pro Q2 Launch Draft"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
                    <label className="block text-xs font-medium text-ink">Channel</label>
                    <select
                      value={channel}
                      onChange={(e) => setChannel(e.target.value)}
                      className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="Advertisement">Advertisement</option>
                      <option value="Website & Landing Page">Website & Landing Page</option>
                      <option value="Press Release">Press Release</option>
                      <option value="Sales Collateral">Sales Collateral</option>
                      <option value="Whitepaper">Technical Whitepaper</option>
                      <option value="Social Media">Social Media</option>
                      <option value="Email Campaign">Email Campaign</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="block text-xs font-medium text-ink">Content Type</label>
                    <select
                      value={contentType}
                      onChange={(e) => setContentType(e.target.value)}
                      className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                    >
                      <option value="Ad Copy">Ad Copy</option>
                      <option value="Landing Page Copy">Landing Page Copy</option>
                      <option value="Press Announcement">Press Announcement</option>
                      <option value="Sales Presentation">Sales Presentation</option>
                      <option value="Whitepaper / Research">Whitepaper / Research</option>
                      <option value="Executive Briefing">Executive Briefing</option>
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

                <div className="pt-2">
                  <label className="block text-xs font-medium text-ink">Purpose / Intent</label>
                  <input
                    type="text"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="e.g. Promote faster employee onboarding, Announce ISO 27001 certification"
                    className="mt-1 w-full bg-paper border border-line-strong rounded-lg px-3 py-2 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
                  />
                  <p className="text-[11px] text-ink-mute mt-1">
                    Stored immutably on the review to provide reviewers and auditors the creator&apos;s strategic intent.
                  </p>
                </div>
              </div>
            </Card>

            <div className="flex items-center justify-between">
              <Button type="button" variant="outline" onClick={() => setCurrentStep(1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back to Content
              </Button>
              <Button type="button" onClick={handleProceedToStep3}>
                Review & Live Scoping <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* STEP 3: CONFIRMATION & LIVE SCOPE */}
        {currentStep === 3 && (
          <div className="space-y-6">
            {/* Context & Document Preview Card */}
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Review Submission Summary</CardTitle>
                  <CardDescription>Confirm draft content and selected governance scopes</CardDescription>
                </div>
                <Badge variant="status" value="Draft">
                  Version 1
                </Badge>
              </CardHeader>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pb-4 border-b border-line">
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-ink-soft">
                    Intent Card Context
                  </h4>
                  <div className="bg-paper rounded-lg p-3 border border-line space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Title:</span>
                      <span className="text-ink font-medium">{title}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Product:</span>
                      <span className="text-accent-ink font-medium">{product}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Region:</span>
                      <span className="text-ink font-medium">{region}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Channel:</span>
                      <span className="text-ink font-medium">{channel}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Audience:</span>
                      <span className="text-ink font-medium">{intendedAudience}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Purpose:</span>
                      <span className="text-ink font-medium line-clamp-1">{purpose}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-ink-soft">
                    Document Payload
                  </h4>
                  <div className="bg-paper rounded-lg p-3 border border-line space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-ink-mute">Source:</span>
                      <span className="text-ink font-medium">
                        {inputMode === "upload" ? "Uploaded File" : "Pasted Content"}
                      </span>
                    </div>
                    {inputMode === "upload" && file ? (
                      <>
                        <div className="flex justify-between">
                          <span className="text-ink-mute">Filename:</span>
                          <span className="text-ink font-mono">{file.name}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-ink-mute">File Size:</span>
                          <span className="text-ink font-mono">
                            {(file.size / 1024).toFixed(1)} KB
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="flex justify-between">
                        <span className="text-ink-mute">Length:</span>
                        <span className="text-ink font-mono">
                          {wordsCount} words ({charsCount} chars)
                        </span>
                      </div>
                    )}
                    <div className="pt-1">
                      <span className="text-ink-mute text-[11px] block mb-1">Preview snippet:</span>
                      <p className="text-[11px] font-mono text-ink-soft bg-surface p-2 rounded line-clamp-2">
                        {inputMode === "upload" && file
                          ? `Binary/document file ${file.name} queued for decomposition.`
                          : pastedText}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* LIVE APPLICABLE KNOWLEDGE SCOPING SECTION */}
              <div className="pt-2 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-accent-ink" />
                    <h4 className="text-xs font-semibold text-ink">
                      Live Applicable Knowledge Scope
                    </h4>
                  </div>
                  <span className="text-[11px] font-mono text-ink-mute">
                    GET /api/v1/knowledge/applicable
                  </span>
                </div>

                {loadingKnowledge ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </div>
                ) : applicableKnowledge ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-paper border border-line">
                      <div className="flex items-center justify-between text-xs text-ink-soft">
                        <span>Approved Facts</span>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      </div>
                      <div className="text-xl font-semibold text-ink mt-1">
                        {applicableKnowledge.counts.facts}
                      </div>
                      <p className="text-[11px] text-ink-mute mt-0.5">Scoped for product/region</p>
                    </div>

                    <div className="p-3 rounded-lg bg-paper border border-line">
                      <div className="flex items-center justify-between text-xs text-ink-soft">
                        <span>Guidelines</span>
                        <BookOpen className="w-3.5 h-3.5 text-accent-ink" />
                      </div>
                      <div className="text-xl font-semibold text-ink mt-1">
                        {applicableKnowledge.counts.guidelines}
                      </div>
                      <p className="text-[11px] text-ink-mute mt-0.5">Brand & regulatory tone</p>
                    </div>

                    <div className="p-3 rounded-lg bg-paper border border-line">
                      <div className="flex items-center justify-between text-xs text-ink-soft">
                        <span>Terminology</span>
                        <Hash className="w-3.5 h-3.5 text-cyan-400" />
                      </div>
                      <div className="text-xl font-semibold text-ink mt-1">
                        {applicableKnowledge.counts.terms}
                      </div>
                      <p className="text-[11px] text-ink-mute mt-0.5">Disallowed variants</p>
                    </div>

                    <div className="p-3 rounded-lg bg-paper border border-line">
                      <div className="flex items-center justify-between text-xs text-ink-soft">
                        <span>Rules Engine</span>
                        <Scale className="w-3.5 h-3.5 text-amber-400" />
                      </div>
                      <div className="text-xl font-semibold text-ink mt-1">
                        {applicableKnowledge.counts.rules}
                      </div>
                      <p className="text-[11px] text-ink-mute mt-0.5">Deterministic checks</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-ink-mute">Could not resolve knowledge scope.</p>
                )}

                {applicableKnowledge && applicableKnowledge.expired_facts_excluded.length > 0 && (
                  <div className="p-2.5 rounded bg-amber-950/20 border border-amber-900/40 text-[11px] text-amber-300 flex items-center justify-between">
                    <span>
                      {applicableKnowledge.expired_facts_excluded.length} expired facts were left out of this scope.
                    </span>
                  </div>
                )}
              </div>
            </Card>

            <div className="flex items-center justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentStep(2)}
                disabled={submitting}
              >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back to Intent Card
              </Button>
              <Button
                type="button"
                onClick={handleSubmitReview}
                isLoading={submitting}
                className="bg-accent hover:bg-accent-hover text-ink font-semibold"
              >
                <ShieldCheck className="w-4 h-4 mr-1.5" />
                Run BrandProof Review
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
