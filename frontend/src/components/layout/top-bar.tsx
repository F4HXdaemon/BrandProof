"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, Menu, X } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { UserRole } from "@/lib/types";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const knowledge = [
  { title: "Facts", href: "/knowledge/facts" },
  { title: "Guidelines", href: "/knowledge/guidelines" },
  { title: "Terminology", href: "/knowledge/terminology" },
  { title: "Rules", href: "/knowledge/rules" },
];

const roles: UserRole[] = ["Admin", "Brand Manager", "Fact Owner", "Reviewer", "Creator"];

/** Close a popover when the user clicks outside it or presses Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

const isDemoEnabled = process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE === "true";

export function TopBar() {
  const pathname = usePathname();
  const { user, logout, quickSwitchDemoUser } = useAuth();
  const [knowledgeOpen, setKnowledgeOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const knowledgeRef = useDismiss(knowledgeOpen, () => setKnowledgeOpen(false));
  const userRef = useDismiss(userOpen, () => setUserOpen(false));

  useEffect(() => {
    setKnowledgeOpen(false);
    setUserOpen(false);
    setMobileOpen(false);
  }, [pathname]);

  const isActive = (href: string) =>
    href === "/dashboard"
      ? pathname === "/dashboard" || pathname === "/"
      : href === "/reviews"
      ? pathname === "/reviews" || (pathname.startsWith("/reviews/") && pathname !== "/reviews/new")
      : pathname.startsWith(href);

  const knowledgeActive = pathname.startsWith("/knowledge");

  const linkClass = (active: boolean) =>
    cn(
      "relative inline-flex h-14 items-center text-sm transition-colors",
      "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:transition-colors",
      active
        ? "text-ink font-medium after:bg-accent"
        : "text-ink-soft hover:text-ink after:bg-transparent"
    );

  const resetDemo = async () => {
    setUserOpen(false);
    if (!window.confirm("Reset all data to the clean Northstar Cloud demo state?")) return;
    setIsResetting(true);
    try {
      await api.demo.reset();
      window.location.reload();
    } catch (err) {
      alert("Reset failed: " + err);
    } finally {
      setIsResetting(false);
    }
  };

  const initial = user?.full_name?.charAt(0) || "U";

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-6">
        <Link href="/dashboard" className="font-serif text-xl font-medium tracking-tight text-ink">
          BrandProof
        </Link>

        {/* Desktop navigation */}
        <nav className="hidden md:flex items-center gap-6 flex-1">
          <Link href="/dashboard" className={linkClass(isActive("/dashboard"))}>
            Overview
          </Link>
          <Link href="/reviews" className={linkClass(isActive("/reviews"))}>
            Reviews
          </Link>

          <div className="relative" ref={knowledgeRef}>
            <button
              onClick={() => setKnowledgeOpen((o) => !o)}
              aria-expanded={knowledgeOpen}
              className={cn(linkClass(knowledgeActive), "gap-1")}
            >
              Knowledge
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", knowledgeOpen && "rotate-180")} />
            </button>
            {knowledgeOpen && (
              <div className="absolute left-0 top-full mt-1 w-44 rounded-lg border border-line bg-surface py-1 shadow-soft">
                {knowledge.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "block px-3 py-2 text-sm hover:bg-sunken",
                      pathname.startsWith(item.href) ? "text-ink font-medium" : "text-ink-soft"
                    )}
                  >
                    {item.title}
                  </Link>
                ))}
              </div>
            )}
          </div>

          <Link href="/insights" className={linkClass(isActive("/insights"))}>
            Insights
          </Link>
          <Link href="/evaluation" className={linkClass(isActive("/evaluation"))}>
            Evaluation
          </Link>
          <Link href="/audit" className={linkClass(isActive("/audit"))}>
            Audit log
          </Link>
        </nav>

        <div className="ml-auto md:ml-0 flex items-center gap-3">
          <Link
            href="/reviews/new"
            className="hidden sm:inline-flex items-center rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-accent-hover"
          >
            New review
          </Link>

          {/* User menu */}
          <div className="relative" ref={userRef}>
            <button
              onClick={() => setUserOpen((o) => !o)}
              aria-expanded={userOpen}
              className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 transition-colors hover:bg-sunken"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent-ink">
                {initial}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-ink-mute" />
            </button>

            {userOpen && (
              <div className="absolute right-0 top-full mt-1 w-60 rounded-lg border border-line bg-surface shadow-soft">
                <div className="px-4 py-3 border-b border-line">
                  <p className="text-sm font-medium text-ink truncate">{user?.full_name}</p>
                  <p className="text-xs text-ink-soft truncate">
                    {user?.role} {user?.title ? `· ${user.title}` : ""}
                  </p>
                </div>

                {isDemoEnabled && (
                  <div className="py-1 border-b border-line">
                    <p className="px-4 pt-2 pb-1 text-xs text-ink-mute">Switch demo role</p>
                    {roles.map((r) => (
                      <button
                        key={r}
                        onClick={() => {
                          setUserOpen(false);
                          quickSwitchDemoUser(r);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between px-4 py-1.5 text-left text-sm hover:bg-sunken",
                          user?.role === r ? "text-ink font-medium" : "text-ink-soft"
                        )}
                      >
                        {r}
                        {user?.role === r && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
                      </button>
                    ))}
                  </div>
                )}

                <div className="py-1">
                  <Link href="/settings" className="block px-4 py-1.5 text-sm text-ink-soft hover:bg-sunken hover:text-ink">
                    Settings
                  </Link>
                  {isDemoEnabled && (
                    <button
                      onClick={resetDemo}
                      disabled={isResetting}
                      className="block w-full px-4 py-1.5 text-left text-sm text-ink-soft hover:bg-sunken hover:text-ink disabled:opacity-50"
                    >
                      {isResetting ? "Resetting…" : "Reset demo data"}
                    </button>
                  )}
                  <button
                    onClick={logout}
                    className="block w-full px-4 py-1.5 text-left text-sm text-ink-soft hover:bg-sunken hover:text-ink"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>

          <button
            className="md:hidden rounded-md p-1.5 text-ink-soft hover:bg-sunken"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile navigation */}
      {mobileOpen && (
        <nav className="md:hidden border-t border-line bg-paper px-6 py-3 space-y-0.5">
          {[
            { title: "Overview", href: "/dashboard" },
            { title: "Reviews", href: "/reviews" },
            { title: "New review", href: "/reviews/new" },
            ...knowledge,
            { title: "Insights", href: "/insights" },
            { title: "Evaluation", href: "/evaluation" },
            { title: "Audit log", href: "/audit" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "block rounded-md px-2 py-2 text-sm",
                pathname === item.href ? "bg-sunken text-ink font-medium" : "text-ink-soft"
              )}
            >
              {item.title}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
