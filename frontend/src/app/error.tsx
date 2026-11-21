"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon, RefreshCw, Home, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error for client-side diagnosis
    console.error("Unhandled client error caught by boundary:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="mx-auto w-14 h-14 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
          <AlertOctagon className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <h1 className="font-serif text-2xl font-medium tracking-tight text-ink">
            Something went wrong
          </h1>
          <p className="text-sm text-ink-soft">
            {error?.message && !error.message.includes("Object")
              ? error.message
              : "An unexpected error occurred while rendering this page. You can try refreshing or returning to the dashboard."}
          </p>
          {error?.digest && (
            <p className="text-[11px] font-mono text-ink-mute">
              Reference code: {error.digest}
            </p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Button
            onClick={() => reset()}
            variant="primary"
            size="sm"
            className="w-full sm:w-auto gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try again
          </Button>

          <Link href="/dashboard" className="w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 border-line-strong hover:bg-sunken text-ink"
            >
              <Home className="w-4 h-4" />
              Dashboard
            </Button>
          </Link>

          <Link href="/login" className="w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 border-line-strong hover:bg-sunken text-ink"
            >
              <LogIn className="w-4 h-4" />
              Sign in
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
