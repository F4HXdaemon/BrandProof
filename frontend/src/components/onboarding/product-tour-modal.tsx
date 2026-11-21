"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  BookOpen,
  Play,
  Scale,
  FileCheck,
  ChevronRight,
  ChevronLeft,
  X,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface ProductTourModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

interface TourStep {
  title: string;
  tagline: string;
  description: string;
  icon: React.ReactNode;
  highlight: string;
  actionHint: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to BrandProof",
    tagline: "Every claim, traced to its source.",
    description:
      "BrandProof protects your brand from unsubstantiated claims and compliance drift. AI proposes. Evidence decides. People approve. No valid source means no approved claim.",
    icon: <ShieldCheck className="w-8 h-8 text-accent" />,
    highlight: "Core Invariant: Zero Hallucinated Claims",
    actionHint: "Takes under 1 minute to explore the key workflow.",
  },
  {
    title: "1. Brand Knowledge Base",
    tagline: "Your verified ground truth registry.",
    description:
      "Register approved enterprise facts, tone guidelines, trademark terminology, and compliance rules. You can add items manually or upload documents and images with instant OCR.",
    icon: <BookOpen className="w-8 h-8 text-blue-400" />,
    highlight: "Method A (Manual) & Method B (OCR / Doc Extraction)",
    actionHint: "Facts, Guidelines, Terminology & Rules Engines.",
  },
  {
    title: "2. Launch Brand Evaluations",
    tagline: "Comprehensive marketing & ad copy audit.",
    description:
      "Submit ad drafts, blog copy, or campaign decks via pasted text or file upload (.pdf, .docx, .txt). BrandProof scopes applicable regional and product knowledge automatically.",
    icon: <Play className="w-8 h-8 text-amber-400" />,
    highlight: "Automated Claim Extraction & Parsing",
    actionHint: "Multi-step wizard with draft autosave.",
  },
  {
    title: "3. CitationGate Invariant",
    tagline: "Strict source-backed verification.",
    description:
      "Every detected statement is verified against active evidence. If a claim references an expired benchmark or lacks verifiable proof, it is flagged with deterministic severity weights.",
    icon: <Scale className="w-8 h-8 text-purple-400" />,
    highlight: "Deterministic Risk Scoring (1 to 15 pts)",
    actionHint: "Full transparency: claims matched directly to evidence.",
  },
  {
    title: "4. Boardroom-Ready Reports",
    tagline: "Download verifiable PDF audit telemetry.",
    description:
      "Export certified PDF reports with executive risk classifications, claims ledgers, verified evidence checksums, and audit trail history ready for legal review.",
    icon: <FileCheck className="w-8 h-8 text-emerald-400" />,
    highlight: "Instant Downloadable PDF Reports",
    actionHint: "Download and share with team members.",
  },
];

export function ProductTourModal({ isOpen, onClose, onComplete }: ProductTourModalProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const handleNext = useCallback(() => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      onComplete();
    }
  }, [currentStep, onComplete]);

  const handlePrev = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowRight") {
        handleNext();
      } else if (e.key === "ArrowLeft") {
        handlePrev();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleNext, handlePrev, onClose]);

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];
  const isLast = currentStep === TOUR_STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      aria-describedby="tour-desc"
    >
      <div className="bg-surface border border-line rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header bar */}
        <div className="px-6 pt-5 pb-3 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-ink-mute">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span className="font-semibold uppercase tracking-wider text-[11px] text-ink-soft">
              BrandProof Product Tour
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-ink-mute hover:text-ink transition-colors p-1 rounded-md"
            aria-label="Close tour"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {/* Step Icon & Category Badge */}
          <div className="flex items-center justify-between">
            <div className="w-14 h-14 rounded-xl bg-sunken border border-line flex items-center justify-center shadow-inner">
              {step.icon}
            </div>
            <span className="text-xs font-mono font-medium text-ink-mute bg-paper border border-line px-2.5 py-1 rounded-full">
              Step {currentStep + 1} of {TOUR_STEPS.length}
            </span>
          </div>

          <div>
            <h2 id="tour-title" className="text-xl font-serif font-semibold text-ink">
              {step.title}
            </h2>
            <p className="text-xs font-medium text-accent-ink mt-0.5">{step.tagline}</p>
            <p id="tour-desc" className="text-sm text-ink-soft leading-relaxed mt-3">
              {step.description}
            </p>
          </div>

          {/* Highlight pill */}
          <div className="p-3 rounded-lg bg-sunken border border-line flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-ink">
              <CheckCircle2 className="w-4 h-4 text-accent-ink shrink-0" />
              <span className="font-medium">{step.highlight}</span>
            </div>
            <span className="text-[11px] text-ink-mute hidden sm:inline">{step.actionHint}</span>
          </div>

          {/* Step Progress Dots */}
          <div className="flex items-center justify-center gap-2 pt-2">
            {TOUR_STEPS.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentStep(i)}
                className={`h-2 rounded-full transition-all duration-300 ${
                  i === currentStep
                    ? "w-8 bg-accent"
                    : "w-2 bg-line hover:bg-line-strong"
                }`}
                aria-label={`Go to step ${i + 1}`}
              />
            ))}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-line bg-paper/60 flex items-center justify-between">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-xs text-ink-mute hover:text-ink"
          >
            Skip Tour
          </Button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handlePrev}
                className="text-xs"
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                Back
              </Button>
            )}

            <Button
              type="button"
              size="sm"
              onClick={handleNext}
              className="text-xs bg-accent text-ink hover:bg-accent-hover font-semibold px-4"
            >
              {isLast ? (
                <>
                  <span>Get Started</span>
                  <Sparkles className="w-3.5 h-3.5 ml-1.5" />
                </>
              ) : (
                <>
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
