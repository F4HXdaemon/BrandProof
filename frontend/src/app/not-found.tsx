import React from "react";
import Link from "next/link";
import { Compass, ArrowLeft, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="mx-auto w-14 h-14 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent-ink">
          <Compass className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-mono font-semibold px-2.5 py-0.5 rounded-full bg-sunken text-ink-soft border border-line">
            404 — Page Not Found
          </span>
          <h1 className="font-serif text-2xl font-medium tracking-tight text-ink mt-3">
            Lost in the ledger?
          </h1>
          <p className="text-sm text-ink-soft">
            The page you requested could not be located. It may have moved or does not exist.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link href="/dashboard" className="w-full sm:w-auto">
            <Button variant="default" size="sm" className="w-full gap-2">
              <Home className="w-4 h-4" />
              Go to Dashboard
            </Button>
          </Link>

          <Link href="/" className="w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 border-line-strong hover:bg-sunken text-ink"
            >
              <ArrowLeft className="w-4 h-4" />
              Landing page
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
