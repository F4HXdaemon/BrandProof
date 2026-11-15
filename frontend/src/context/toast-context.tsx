"use client";

import React, { createContext, useContext, useState } from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";

export type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  title: string;
  message?: string;
  type: ToastType;
}

interface ToastContextType {
  toast: (title: string, message?: string, type?: ToastType) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const addToast = (
    title: string,
    message?: string,
    type: ToastType = "info"
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, title, message, type }]);

    setTimeout(() => {
      removeToast(id);
    }, 4500);
  };

  return (
    <ToastContext.Provider
      value={{
        toast: addToast,
        success: (title, message) => addToast(title, message, "success"),
        error: (title, message) => addToast(title, message, "error"),
        info: (title, message) => addToast(title, message, "info"),
        warning: (title, message) => addToast(title, message, "warning"),
      }}
    >
      {children}
      {/* Toast Render Container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-lg border shadow-soft ${
              t.type === "success"
                ? "bg-surface text-ink border-emerald-500/40"
                : t.type === "error"
                ? "bg-surface text-ink border-rose-500/40"
                : t.type === "warning"
                ? "bg-surface text-ink border-amber-500/40"
                : "bg-surface text-ink border-accent/40"
            }`}
          >
            <div className="mt-0.5 shrink-0">
              {t.type === "success" && (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              )}
              {t.type === "error" && (
                <AlertCircle className="w-5 h-5 text-rose-400" />
              )}
              {t.type === "warning" && (
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              )}
              {t.type === "info" && (
                <Info className="w-5 h-5 text-accent-ink" />
              )}
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold">{t.title}</p>
              {t.message && (
                <p className="text-xs text-ink-soft mt-0.5">{t.message}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(t.id)}
              className="text-ink-soft hover:text-ink transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
