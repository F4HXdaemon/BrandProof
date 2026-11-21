"use client";

import React, { useState, useRef } from "react";
import {
  Upload,
  FileText,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  FileCode,
  X,
  Shield,
  Hash,
  BookOpen,
  Scale,
  Calendar,
  Layers,
  ChevronDown,
  ChevronUp,
  Clock,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import {
  KnowledgeExtractionResult,
  SeverityLevel,
  RuleType,
  FactStatus,
} from "@/lib/types";
import { formatBytes } from "@/lib/utils";

interface KnowledgeUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetCategory: "fact" | "guideline" | "term" | "rule";
  onItemCreated: () => void;
}

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15MB
const ALLOWED_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".pdf",
  ".docx",
  ".txt",
  ".text",
  ".md",
  ".markdown",
];

export function KnowledgeUploadModal({
  isOpen,
  onClose,
  targetCategory,
  onItemCreated,
}: KnowledgeUploadModalProps) {
  const { success, error, warning } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<"upload" | "extracting" | "review">("upload");
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);

  // Extraction results
  const [extractionResult, setExtractionResult] = useState<KnowledgeExtractionResult | null>(null);
  const [showExtractedText, setShowExtractedText] = useState(false);
  const [candidateIndex, setCandidateIndex] = useState(0);

  // Editable Form State
  const [title, setTitle] = useState("");
  const [canonicalValue, setCanonicalValue] = useState("");
  const [description, setDescription] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [productScope, setProductScope] = useState("All");
  const [regionScope, setRegionScope] = useState("Global");
  const [channelScope, setChannelScope] = useState("All");
  const [expiresAt, setExpiresAt] = useState("");

  // Guideline specific
  const [principle, setPrinciple] = useState("");
  const [guidelineCategory, setGuidelineCategory] = useState("Brand Voice");
  const [severity, setSeverity] = useState<SeverityLevel>("High");
  const [doExamples, setDoExamples] = useState("");
  const [dontExamples, setDontExamples] = useState("");

  // Term specific
  const [approvedTerm, setApprovedTerm] = useState("");
  const [disallowedVariants, setDisallowedVariants] = useState("");
  const [replacement, setReplacement] = useState("");
  const [notes, setNotes] = useState("");

  // Rule specific
  const [ruleName, setRuleName] = useState("");
  const [ruleType, setRuleType] = useState<string>("FORBIDDEN_PHRASE");
  const [ruleSeverity, setRuleSeverity] = useState<SeverityLevel>("Blocker");
  const [ruleLogic, setRuleLogic] = useState("");

  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const resetState = () => {
    setStep("upload");
    setSelectedFile(null);
    setImagePreviewUrl(null);
    setExtractionResult(null);
    setShowExtractedText(false);
    setCandidateIndex(0);
    setTitle("");
    setCanonicalValue("");
    setDescription("");
    setSourceReference("");
    setProductScope("All");
    setRegionScope("Global");
    setChannelScope("All");
    setExpiresAt("");
    setPrinciple("");
    setGuidelineCategory("Brand Voice");
    setSeverity("High");
    setDoExamples("");
    setDontExamples("");
    setApprovedTerm("");
    setDisallowedVariants("");
    setReplacement("");
    setNotes("");
    setRuleName("");
    setRuleType("FORBIDDEN_PHRASE");
    setRuleSeverity("Blocker");
    setRuleLogic("");
    setIsSaving(false);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const validateAndSelectFile = (file: File) => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      warning(
        "Unsupported Format",
        `File '${file.name}' is not supported. Please upload PNG, JPG, JPEG, WEBP, PDF, DOCX, TXT, or MD.`
      );
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      warning("File Exceeds Limit", `File size exceeds 15 MB limit.`);
      return;
    }

    setSelectedFile(file);
    if (file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setImagePreviewUrl(url);
    } else {
      setImagePreviewUrl(null);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  // Populate candidate data into form fields
  const applyCandidateData = (res: KnowledgeExtractionResult, idx: number) => {
    if (targetCategory === "fact") {
      const candidates = res.suggested_facts || [];
      const item = candidates[idx] || {
        title: `Fact from ${res.filename}`,
        canonical_value: res.extracted_text.slice(0, 150),
        description: `Extracted from ${res.filename}`,
        source_reference: `Evidence [${res.filename}] (ID: ${res.evidence_id.slice(0, 8)})`,
        product_scope: "All",
        region_scope: "Global",
        channel_scope: "All",
      };
      setTitle(item.title);
      setCanonicalValue(item.canonical_value);
      setDescription(item.description || `Extracted from ${res.filename}`);
      setSourceReference(item.source_reference);
      setProductScope(item.product_scope || "All");
      setRegionScope(item.region_scope || "Global");
      setChannelScope(item.channel_scope || "All");
      setExpiresAt(item.expires_at || "");
    } else if (targetCategory === "guideline") {
      const candidates = res.suggested_guidelines || [];
      const item = candidates[idx] || {
        title: `Guideline from ${res.filename}`,
        principle: "Maintain approved brand voice and compliance standards.",
        category: "Brand Voice",
        severity: "High" as SeverityLevel,
        description: `Extracted from ${res.filename}`,
        do_examples: ["Use verified phrasing."],
        dont_examples: ["Avoid unsubstantiated claims."],
        source_reference: `Evidence [${res.filename}] (ID: ${res.evidence_id.slice(0, 8)})`,
        product_scope: "All",
        region_scope: "Global",
        channel_scope: "All",
      };
      setTitle(item.title);
      setPrinciple(item.principle);
      setGuidelineCategory(item.category || "Brand Voice");
      setSeverity(item.severity || "High");
      setDescription(item.description);
      setDoExamples(item.do_examples ? item.do_examples.join("\n") : "");
      setDontExamples(item.dont_examples ? item.dont_examples.join("\n") : "");
      setSourceReference(item.source_reference);
      setProductScope(item.product_scope || "All");
      setRegionScope(item.region_scope || "Global");
      setChannelScope(item.channel_scope || "All");
    } else if (targetCategory === "term") {
      const candidates = res.suggested_terms || [];
      const item = candidates[idx] || {
        approved_term: res.filename.replace(/\.[^/.]+$/, ""),
        disallowed_variants: [res.filename.toLowerCase()],
        replacement: res.filename.replace(/\.[^/.]+$/, ""),
        notes: `Extracted from ${res.filename}`,
        source_reference: `Evidence [${res.filename}] (ID: ${res.evidence_id.slice(0, 8)})`,
        product_scope: "All",
        region_scope: "Global",
        channel_scope: "All",
      };
      setApprovedTerm(item.approved_term);
      setDisallowedVariants(item.disallowed_variants ? item.disallowed_variants.join(", ") : "");
      setReplacement(item.replacement || item.approved_term);
      setNotes(item.notes || `Extracted from ${res.filename}`);
      setSourceReference(item.source_reference);
      setProductScope(item.product_scope || "All");
      setRegionScope(item.region_scope || "Global");
      setChannelScope(item.channel_scope || "All");
    } else if (targetCategory === "rule") {
      const candidates = res.suggested_rules || [];
      const item = candidates[idx] || {
        name: `Rule from ${res.filename}`,
        rule_type: "FORBIDDEN_PHRASE",
        severity: "Blocker" as SeverityLevel,
        description: `Deterministic check from ${res.filename}`,
        configuration: { forbidden_phrases: ["unverified claim"] },
        source_reference: `Evidence [${res.filename}] (ID: ${res.evidence_id.slice(0, 8)})`,
        product_scope: "All",
        region_scope: "Global",
        channel_scope: "All",
      };
      setRuleName(item.name);
      setRuleType(item.rule_type);
      setRuleSeverity(item.severity || "Blocker");
      setDescription(item.description);
      setRuleLogic(
        item.configuration
          ? item.configuration.forbidden_phrases
            ? item.configuration.forbidden_phrases.join(", ")
            : JSON.stringify(item.configuration)
          : ""
      );
      setSourceReference(item.source_reference);
      setProductScope(item.product_scope || "All");
      setRegionScope(item.region_scope || "Global");
      setChannelScope(item.channel_scope || "All");
    }
  };

  // Launch Extraction
  const handleExtract = async () => {
    if (!selectedFile) {
      warning("File Required", "Please choose a document or image to extract knowledge from.");
      return;
    }

    setStep("extracting");
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("target_category", targetCategory);

      const res = await api.knowledge.extract(formData);
      setExtractionResult(res);
      setCandidateIndex(0);
      applyCandidateData(res, 0);
      setStep("review");
      success(
        "Content Extracted",
        `Extracted ${res.word_count} words from ${res.filename}. Review proposed candidates below.`
      );
    } catch (err: any) {
      error("Extraction Failed", err.message || "Could not extract readable text from document.");
      setStep("upload");
    }
  };

  // Save to Active Knowledge Base
  const handleSaveToKnowledgeBase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!extractionResult) return;

    setIsSaving(true);
    try {
      if (targetCategory === "fact") {
        if (!title.trim() || !canonicalValue.trim()) {
          warning("Validation Error", "Title and Canonical Value are required.");
          setIsSaving(false);
          return;
        }

        await api.facts.create({
          title: title.trim(),
          canonical_value: canonicalValue.trim(),
          description: description.trim() || undefined,
          source_reference: sourceReference.trim() || `Evidence [${extractionResult.filename}]`,
          product_scope: productScope.trim() || "All",
          region_scope: regionScope.trim() || "Global",
          channel_scope: channelScope.trim() || "All",
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
          status: "Approved",
        });

        success("Approved Fact Created", `Successfully saved fact "${title}" to knowledge base.`);
      } else if (targetCategory === "guideline") {
        if (!title.trim() || !description.trim()) {
          warning("Validation Error", "Title and Description are required.");
          setIsSaving(false);
          return;
        }

        let fullDescription = description.trim();
        if (principle.trim() && !fullDescription.includes(principle.trim())) {
          fullDescription = `${principle.trim()}\n\n${fullDescription}`;
        }
        if (doExamples.trim()) {
          fullDescription = `${fullDescription}\n\nDO:\n${doExamples.trim()}`;
        }
        if (dontExamples.trim()) {
          fullDescription = `${fullDescription}\n\nDON'T:\n${dontExamples.trim()}`;
        }

        await api.guidelines.create({
          title: title.trim(),
          category: guidelineCategory,
          severity: severity,
          description: fullDescription,
          source_reference: sourceReference.trim() || `Evidence [${extractionResult.filename}]`,
          product_scope: productScope.trim() || "All",
          region_scope: regionScope.trim() || "Global",
          channel_scope: channelScope.trim() || "All",
          status: "Approved",
          active: true,
        });

        success("Guideline Created", `Successfully saved guideline "${title}" to knowledge base.`);
      } else if (targetCategory === "term") {
        if (!approvedTerm.trim()) {
          warning("Validation Error", "Approved Term is required.");
          setIsSaving(false);
          return;
        }

        const variants = disallowedVariants
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

        const combinedNotes = notes.trim()
          ? `${notes.trim()} (Source: ${sourceReference.trim() || extractionResult.filename})`
          : `Evidence [${extractionResult.filename}]`;

        await api.terms.create({
          approved_term: approvedTerm.trim(),
          disallowed_variants: variants,
          replacement: replacement.trim() || approvedTerm.trim(),
          notes: combinedNotes,
          product_scope: productScope.trim() || "All",
          region_scope: regionScope.trim() || "Global",
          channel_scope: channelScope.trim() || "All",
          status: "Approved",
          active: true,
        });

        success("Terminology Created", `Successfully saved term "${approvedTerm}" to knowledge base.`);
      } else if (targetCategory === "rule") {
        if (!ruleName.trim()) {
          warning("Validation Error", "Rule Name is required.");
          setIsSaving(false);
          return;
        }

        let config: Record<string, any> = {};
        if (ruleType === "FORBIDDEN_PHRASE") {
          const phrases = ruleLogic
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          config = { forbidden_phrases: phrases.length > 0 ? phrases : [ruleLogic.trim()] };
        } else if (ruleType === "REQUIRED_DISCLAIMER") {
          const terms = ruleLogic
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          config = { required_terms: terms };
        } else {
          config = { pattern: ruleLogic.trim() };
        }

        await api.rules.create({
          name: ruleName.trim(),
          rule_type: ruleType,
          severity: ruleSeverity,
          description: description.trim() || `Governance rule from ${extractionResult.filename}`,
          configuration: config,
          source_reference: sourceReference.trim() || `Evidence [${extractionResult.filename}]`,
          product_scope: productScope.trim() || "All",
          region_scope: regionScope.trim() || "Global",
          channel_scope: channelScope.trim() || "All",
          status: "Approved",
          active: true,
        });

        success("Governance Rule Created", `Successfully saved rule "${ruleName}" to knowledge base.`);
      }

      onItemCreated();
      handleClose();
    } catch (err: any) {
      error("Save Failed", err.message || "Failed to commit knowledge item to database.");
      setIsSaving(false);
    }
  };

  const getCandidateCount = () => {
    if (!extractionResult) return 0;
    if (targetCategory === "fact") return (extractionResult.suggested_facts || []).length;
    if (targetCategory === "guideline") return (extractionResult.suggested_guidelines || []).length;
    if (targetCategory === "term") return (extractionResult.suggested_terms || []).length;
    if (targetCategory === "rule") return (extractionResult.suggested_rules || []).length;
    return 0;
  };

  const candidateCount = getCandidateCount();

  const getCategoryTitle = () => {
    if (targetCategory === "fact") return "Approved Fact";
    if (targetCategory === "guideline") return "Brand Guideline";
    if (targetCategory === "term") return "Brand Terminology";
    if (targetCategory === "rule") return "Governance Rule";
    return "Knowledge Item";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface border border-line-strong rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-paper">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center text-accent-ink">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">
                Add {getCategoryTitle()} via Document or Image
              </h3>
              <p className="text-xs text-ink-soft">
                Method B: Upload source document or image, extract text, review & approve.
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="text-ink-mute hover:text-ink p-1 rounded-lg hover:bg-sunken transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* STEP 1: UPLOAD */}
          {step === "upload" && (
            <div className="space-y-4">
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  dragActive
                    ? "border-accent bg-accent-soft/30"
                    : selectedFile
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-line-strong hover:border-accent/60 bg-paper"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.txt,.text,.md,.markdown"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      validateAndSelectFile(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />

                {selectedFile ? (
                  <div className="space-y-3">
                    {imagePreviewUrl ? (
                      <div className="w-24 h-24 mx-auto rounded-lg overflow-hidden border border-line bg-sunken flex items-center justify-center">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={imagePreviewUrl}
                          alt="Uploaded asset preview"
                          className="w-full h-full object-cover"
                        />
                      </div>
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
                        <FileText className="w-6 h-6" />
                      </div>
                    )}
                    <div>
                      <p className="text-sm font-semibold text-ink">{selectedFile.name}</p>
                      <p className="text-xs text-ink-mute">
                        {formatBytes(selectedFile.size)} • Ready for OCR & Document Extraction
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                      className="text-xs"
                    >
                      Choose Different File
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="w-12 h-12 rounded-lg bg-accent/10 border border-accent/30 text-accent-ink mx-auto flex items-center justify-center">
                      <Upload className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        Drag and drop source document or image here
                      </p>
                      <p className="text-xs text-ink-soft mt-1">
                        Supports images (PNG, JPG, JPEG, WEBP) and documents (PDF, DOCX, TXT, MD) up to 15 MB
                      </p>
                    </div>
                    <Button type="button" variant="outline" size="sm" className="text-xs">
                      Browse Files
                    </Button>
                  </div>
                )}
              </div>

              {/* Supported Guidelines Box */}
              <div className="p-3.5 rounded-lg bg-sunken border border-line text-xs text-ink-soft space-y-1.5">
                <div className="flex items-center gap-2 text-ink font-semibold">
                  <Shield className="w-3.5 h-3.5 text-accent-ink" />
                  <span>Enterprise Evidence Traceability & CitationGate</span>
                </div>
                <p className="text-[11px] text-ink-mute">
                  The uploaded file is deeply inspected, validated for magic bytes, and hashed (SHA-256).
                  Readable text is extracted via OCR / parsers and formatted into prospective candidates.
                  You must explicitly review and confirm all fields before they become approved knowledge.
                </p>
              </div>
            </div>
          )}

          {/* STEP 2: EXTRACTING SPINNER */}
          {step === "extracting" && (
            <div className="py-12 text-center space-y-4">
              <div className="w-12 h-12 rounded-xl bg-accent/20 border border-accent/40 flex items-center justify-center mx-auto text-accent-ink animate-spin">
                <Sparkles className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-ink">
                  Extracting Content from {selectedFile?.name}...
                </h4>
                <p className="text-xs text-ink-soft">
                  Executing document parsing, OCR text analysis, and candidate synthesis.
                </p>
              </div>
            </div>
          )}

          {/* STEP 3: REVIEW & HUMAN CONFIRMATION */}
          {step === "review" && extractionResult && (
            <form onSubmit={handleSaveToKnowledgeBase} className="space-y-4">
              {/* Evidence Traceability Bar */}
              <div className="p-3 rounded-lg bg-paper border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded bg-accent/20 border border-accent/30 flex items-center justify-center text-accent-ink shrink-0">
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="font-semibold text-ink">{extractionResult.filename}</span>
                    <span className="text-[11px] text-ink-mute ml-2">
                      ({formatBytes(extractionResult.file_size)} • {extractionResult.word_count} words extracted)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono bg-sunken px-2 py-0.5 rounded text-ink-mute border border-line">
                    SHA: {extractionResult.file_hash ? extractionResult.file_hash.slice(0, 10) + "..." : "verified"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowExtractedText(!showExtractedText)}
                    className="text-accent-ink hover:underline text-[11px] inline-flex items-center gap-1 font-medium"
                  >
                    <span>{showExtractedText ? "Hide Text" : "View Extracted Text"}</span>
                    {showExtractedText ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                </div>
              </div>

              {/* Collapsible Extracted Text Viewer */}
              {showExtractedText && (
                <div className="space-y-1 animate-in fade-in">
                  <label className="text-[11px] font-semibold text-ink-soft">
                    Raw Extracted Text (OCR / Parser Output)
                  </label>
                  <textarea
                    rows={4}
                    readOnly
                    value={extractionResult.extracted_text}
                    className="w-full bg-sunken border border-line rounded-lg p-2.5 text-xs text-ink font-mono focus:outline-none"
                  />
                </div>
              )}

              {/* Candidate Switcher if multiple detected */}
              {candidateCount > 1 && (
                <div className="flex items-center justify-between bg-sunken/60 p-2.5 rounded-lg border border-line text-xs">
                  <span className="text-ink-soft font-medium">
                    Found {candidateCount} prospective candidate(s). Reviewing #{candidateIndex + 1}:
                  </span>
                  <div className="flex items-center gap-1.5">
                    {Array.from({ length: candidateCount }).map((_, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => {
                          setCandidateIndex(i);
                          applyCandidateData(extractionResult, i);
                        }}
                        className={`px-2.5 py-0.5 rounded text-xs font-mono font-medium transition-colors ${
                          candidateIndex === i
                            ? "bg-accent text-ink"
                            : "bg-surface border border-line text-ink-soft hover:text-ink"
                        }`}
                      >
                        #{i + 1}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* EDITABLE FORM FIELDS ACCORDING TO CATEGORY */}

              {/* 1. FACT FIELDS */}
              {targetCategory === "fact" && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Fact Title / Summary <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Employee Onboarding Time Reduction"
                      className="w-full bg-paper border border-line rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Canonical Value / Approved Factual Claim <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      required
                      rows={2}
                      value={canonicalValue}
                      onChange={(e) => setCanonicalValue(e.target.value)}
                      placeholder="e.g. Cuts employee onboarding time by 60% with automated workflow triggers."
                      className="w-full bg-paper border border-line rounded-lg p-2.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">Product Scope</label>
                      <input
                        type="text"
                        value={productScope}
                        onChange={(e) => setProductScope(e.target.value)}
                        placeholder="All or Product Name"
                        className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">Region Scope</label>
                      <input
                        type="text"
                        value={regionScope}
                        onChange={(e) => setRegionScope(e.target.value)}
                        placeholder="Global or Region"
                        className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">Expires At (Optional)</label>
                      <input
                        type="date"
                        value={expiresAt}
                        onChange={(e) => setExpiresAt(e.target.value)}
                        className="w-full bg-paper border border-line rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Source Reference (Evidence Link) <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={sourceReference}
                      onChange={(e) => setSourceReference(e.target.value)}
                      placeholder="e.g. Evidence [launch_deck.pdf] (ID: 8a7f920b)"
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink font-mono focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>
              )}

              {/* 2. GUIDELINE FIELDS */}
              {targetCategory === "guideline" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">
                        Guideline Name <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Objective Enterprise Voice"
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">Category</label>
                      <select
                        value={guidelineCategory}
                        onChange={(e) => setGuidelineCategory(e.target.value)}
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      >
                        <option value="Brand Voice">Brand Voice</option>
                        <option value="Marketing Claims">Marketing Claims</option>
                        <option value="Legal & Regulatory">Legal & Regulatory</option>
                        <option value="Visual & Design">Visual & Design</option>
                        <option value="Accessibility">Accessibility</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Description & Context <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      required
                      rows={2}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Guideline rules and explanation."
                      className="w-full bg-paper border border-line rounded-lg p-2 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-emerald-400 block mb-1">
                        DO Examples (One per line)
                      </label>
                      <textarea
                        rows={2}
                        value={doExamples}
                        onChange={(e) => setDoExamples(e.target.value)}
                        placeholder="Verified uptime of 99.9%."
                        className="w-full bg-paper border border-line rounded-lg p-2 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-rose-400 block mb-1">
                        DON&apos;T Examples (One per line)
                      </label>
                      <textarea
                        rows={2}
                        value={dontExamples}
                        onChange={(e) => setDontExamples(e.target.value)}
                        placeholder="Miraculous 100% bug-free platform."
                        className="w-full bg-paper border border-line rounded-lg p-2 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">Source Reference</label>
                    <input
                      type="text"
                      value={sourceReference}
                      onChange={(e) => setSourceReference(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink font-mono focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>
              )}

              {/* 3. TERMINOLOGY FIELDS */}
              {targetCategory === "term" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">
                        Approved Brand Term <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={approvedTerm}
                        onChange={(e) => setApprovedTerm(e.target.value)}
                        placeholder="e.g. BrandProof Pro"
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">
                        Preferred Replacement
                      </label>
                      <input
                        type="text"
                        value={replacement}
                        onChange={(e) => setReplacement(e.target.value)}
                        placeholder="e.g. BrandProof Pro"
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Disallowed Variants (Comma separated) <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={disallowedVariants}
                      onChange={(e) => setDisallowedVariants(e.target.value)}
                      placeholder="e.g. Brand Proof, brandproof pro, BP Pro"
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">Usage Notes & Context</label>
                    <textarea
                      rows={2}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Definition and appropriate usage guidance."
                      className="w-full bg-paper border border-line rounded-lg p-2 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">Source Reference</label>
                    <input
                      type="text"
                      value={sourceReference}
                      onChange={(e) => setSourceReference(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink font-mono focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>
              )}

              {/* 4. RULES FIELDS */}
              {targetCategory === "rule" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">
                        Rule Name <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={ruleName}
                        onChange={(e) => setRuleName(e.target.value)}
                        placeholder="e.g. Prohibit Unsubstantiated Guarantees"
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-ink block mb-1">Rule Type</label>
                      <select
                        value={ruleType}
                        onChange={(e) => setRuleType(e.target.value)}
                        className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                      >
                        <option value="FORBIDDEN_PHRASE">FORBIDDEN_PHRASE</option>
                        <option value="REQUIRED_DISCLAIMER">REQUIRED_DISCLAIMER</option>
                        <option value="TERM_CHECK">TERM_CHECK</option>
                        <option value="REGEX">REGEX</option>
                        <option value="ACCESSIBILITY">ACCESSIBILITY</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">
                      Enforced Phrases / Logic <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={ruleLogic}
                      onChange={(e) => setRuleLogic(e.target.value)}
                      placeholder="e.g. guaranteed, 100% bug-free, zero risk"
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">Description</label>
                    <textarea
                      rows={2}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Rule explanation and policy reference."
                      className="w-full bg-paper border border-line rounded-lg p-2 text-xs text-ink focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-ink block mb-1">Source Reference</label>
                    <input
                      type="text"
                      value={sourceReference}
                      onChange={(e) => setSourceReference(e.target.value)}
                      className="w-full bg-paper border border-line rounded-lg px-3 py-1.5 text-xs text-ink font-mono focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>
              )}

              {/* Invariant Warning */}
              <div className="p-3 rounded-lg bg-accent-soft/30 border border-accent/40 text-[11px] text-ink-soft flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-accent-ink shrink-0 mt-0.5" />
                <span>
                  <strong>Human Approval Required:</strong> You are approving this item from evidence{" "}
                  <code>{extractionResult.filename}</code>. Once committed, it becomes active in your
                  organization&apos;s knowledge base and will be used by CitationGate to verify marketing claims.
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-2 border-t border-line">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setStep("upload")}
                  disabled={isSaving}
                  className="text-xs"
                >
                  Back to Upload
                </Button>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleClose}
                    disabled={isSaving}
                    className="text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    isLoading={isSaving}
                    disabled={isSaving}
                    className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve & Save {getCategoryTitle()}
                  </Button>
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Footer for Step 1 */}
        {step === "upload" && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-line bg-paper">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose} className="text-xs">
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleExtract}
              disabled={!selectedFile}
              className="bg-accent hover:bg-accent-hover text-ink font-semibold text-xs gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Extract Knowledge Candidates
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
