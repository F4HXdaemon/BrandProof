"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Building2,
  Users,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  KeyRound,
  Sparkles,
  Clock,
  AlertCircle,
  Loader2,
  Check,
  Layers,
  Crown,
  ChevronRight,
  Mail,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { UserOrganization, OrganizationInvitation, InviteInfo, UserRole } from "@/lib/types";
import { Button } from "@/components/ui/button";

const inputClass =
  "mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";

export default function OnboardingPage() {
  const { user, isAuthenticated, isLoading, refreshOrganizations } = useAuth();
  const { success, error, info: toastInfo } = useToast();
  const router = useRouter();

  // Organization membership state
  const [myOrgs, setMyOrgs] = useState<UserOrganization[]>([]);
  const [myInvites, setMyInvites] = useState<OrganizationInvitation[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // View state: "select" (if has orgs), "options" (the 2 choices), "create" (form A), "join" (form B)
  const [viewMode, setViewMode] = useState<"select" | "options" | "create" | "join">("options");

  // Form A: Create Organization State
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [createDomain, setCreateDomain] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Form B: Join via Invitation Code State
  const [inviteCode, setInviteCode] = useState("");
  const [isValidatingCode, setIsValidatingCode] = useState(false);
  const [validatedInvite, setValidatedInvite] = useState<InviteInfo | null>(null);
  const [selectedRole, setSelectedRole] = useState<UserRole | "">("");
  const [isJoining, setIsJoining] = useState(false);
  const [joinSuccessState, setJoinSuccessState] = useState<{
    status: "active" | "pending_approval";
    message: string;
    orgName: string;
  } | null>(null);

  // Code Validation Handler
  const validateCode = useCallback(async (codeToValidate: string) => {
    const clean = codeToValidate.trim();
    if (!clean) {
      error("Invitation Code Required", "Please enter a valid invitation code or link.");
      return;
    }

    setIsValidatingCode(true);
    setValidatedInvite(null);
    setJoinSuccessState(null);
    try {
      const res = await api.organizations.validateInvite(clean);
      if (!res.valid) {
        error("Invalid Invitation", "This invitation code is invalid or has expired.");
      } else {
        setValidatedInvite(res);
        // Default role selection
        if (res.allowed_roles && res.allowed_roles.length > 0) {
          setSelectedRole(res.allowed_roles[0]);
        } else if (res.role) {
          setSelectedRole(res.role as UserRole);
        } else {
          setSelectedRole("Creator");
        }
        toastInfo("Invitation Verified", `Valid invitation found for ${res.organization_name}!`);
      }
    } catch (err: any) {
      error("Validation Failed", err.message || "Invitation code could not be verified.");
    } finally {
      setIsValidatingCode(false);
    }
  }, [error, toastInfo]);

  // Check initial memberships and URL params
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/onboarding");
      return;
    }

    async function loadInitialData() {
      try {
        const [orgs, invites] = await Promise.all([
          api.organizations.getMyOrganizations().catch(() => []),
          api.organizations.getMyInvitations().catch(() => []),
        ]);
        setMyOrgs(orgs);
        setMyInvites(invites);

        // If user already belongs to organisations and didn't specify ?action=create or ?action=join
        const params = new URLSearchParams(window.location.search);
        const actionParam = params.get("action");
        const codeParam = params.get("code") || params.get("invite");

        if (codeParam) {
          setInviteCode(codeParam);
          setViewMode("join");
          validateCode(codeParam);
        } else if (actionParam === "create") {
          setViewMode("create");
        } else if (actionParam === "join") {
          setViewMode("join");
        } else if (orgs.length > 0) {
          setViewMode("select");
        } else {
          setViewMode("options");
        }
      } catch (err: any) {
        console.error("Error loading onboarding data:", err);
      } finally {
        setLoadingData(false);
      }
    }

    if (isAuthenticated) {
      loadInitialData();
    }
  }, [isLoading, isAuthenticated, router, validateCode]);

  // Create Organization Handler (Option A)
  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createName.trim() || createName.trim().length < 2) {
      error("Invalid Name", "Organisation name must be at least 2 characters.");
      return;
    }

    setIsCreating(true);
    try {
      const res = await api.organizations.createOrganization({
        name: createName.trim(),
        slug: createSlug.trim() || undefined,
        domain: createDomain.trim() || undefined,
      });

      success(
        "Organisation Created",
        `Welcome to ${res.organization.name}! You are registered as the Organization Owner.`
      );
      await refreshOrganizations();
      router.push("/dashboard");
    } catch (err: any) {
      error("Creation Failed", err.message || "Failed to create organisation.");
    } finally {
      setIsCreating(false);
    }
  };

  // Join Organization Handler (Option B)
  const handleJoinOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validatedInvite) {
      error("Validation Required", "Please validate your invitation code before joining.");
      return;
    }

    setIsJoining(true);
    try {
      const res = await api.organizations.joinWithInvite({
        code: inviteCode.trim(),
        role: selectedRole ? (selectedRole as UserRole) : undefined,
      });

      if (res.status === "active") {
        success(
          "Welcome to the Team!",
          res.message || `Successfully joined ${validatedInvite.organization_name}.`
        );
        await refreshOrganizations();
        router.push("/dashboard");
      } else {
        // Pending approval flow
        setJoinSuccessState({
          status: "pending_approval",
          message: res.message,
          orgName: validatedInvite.organization_name,
        });
        toastInfo(
          "Request Submitted",
          "Your membership request is awaiting administrator approval."
        );
      }
    } catch (err: any) {
      error("Failed to Join", err.message || "An error occurred while joining the organization.");
    } finally {
      setIsJoining(false);
    }
  };

  // Select an existing organization
  const handleSelectOrg = async (orgId: string) => {
    try {
      await api.organizations.switchOrganization(orgId);
      await refreshOrganizations();
      router.push("/dashboard");
    } catch (err: any) {
      error("Switch Failed", err.message || "Could not switch to selected organisation.");
    }
  };

  if (isLoading || loadingData) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <p className="text-xs text-ink-mute font-medium">Loading your BrandProof workspace options…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col justify-between">
      {/* Header */}
      <header className="border-b border-line bg-surface/50 backdrop-blur-sm sticky top-0 z-20">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link href="/" className="font-serif text-xl font-medium tracking-tight text-ink flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-accent-ink" />
            <span>BrandProof</span>
          </Link>

          <div className="flex items-center gap-3 text-xs">
            {user && (
              <span className="text-ink-soft hidden sm:inline">
                Signed in as <strong className="text-ink">{user.email}</strong>
              </span>
            )}
            {myOrgs.length > 0 && viewMode !== "select" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setViewMode("select")}
                className="text-xs"
              >
                My Organisations ({myOrgs.length})
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-10">
        {/* Pending Invitations Alert Banner */}
        {myInvites.length > 0 && (
          <div className="mb-8 rounded-xl border border-accent/30 bg-accent-soft p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Mail className="w-5 h-5 text-accent-ink shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-accent-ink">
                    You have {myInvites.length} pending organisation invitation{myInvites.length > 1 ? "s" : ""}
                  </h4>
                  <p className="text-xs text-ink-soft mt-0.5">
                    You have been invited to join{" "}
                    <strong>{myInvites.map((i) => i.organization_name || "an organisation").join(", ")}</strong>.
                  </p>
                </div>
              </div>
              <Button
                size="sm"
                onClick={() => {
                  if (myInvites[0]?.invitation_code || myInvites[0]?.invite_token) {
                    const code = myInvites[0].invitation_code || myInvites[0].invite_token || "";
                    setInviteCode(code);
                    setViewMode("join");
                    validateCode(code);
                  }
                }}
                className="shrink-0 text-xs"
              >
                Review Invite &rarr;
              </Button>
            </div>
          </div>
        )}

        {/* VIEW 1: SELECT EXISTING ORGANISATION */}
        {viewMode === "select" && myOrgs.length > 0 && (
          <div className="space-y-6">
            <div className="text-center max-w-md mx-auto">
              <h1 className="text-2xl font-serif font-medium text-ink">Select an Organisation</h1>
              <p className="text-xs text-ink-soft mt-1.5">
                You belong to the following BrandProof workspaces. Choose an organisation to enter your dashboard.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto pt-2">
              {myOrgs.map((o) => (
                <div
                  key={o.id}
                  onClick={() => handleSelectOrg(o.id)}
                  className={`group relative rounded-xl border p-5 transition-all cursor-pointer flex flex-col justify-between ${
                    o.is_current
                      ? "border-accent bg-accent-soft/40 shadow-sm"
                      : "border-line bg-surface hover:border-line-strong hover:shadow-md"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface border border-line shadow-xs text-ink font-semibold text-sm">
                        {o.name.charAt(0).toUpperCase()}
                      </div>
                      <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5 text-[11px] font-semibold text-accent-ink border border-line">
                        {o.is_owner ? <Crown className="w-3 h-3" /> : <ShieldCheck className="w-3 h-3" />}
                        {o.role}
                      </span>
                    </div>

                    <h3 className="font-semibold text-ink group-hover:text-accent-ink transition-colors">
                      {o.name}
                    </h3>
                    <p className="text-[11px] font-mono text-ink-mute mt-0.5">/{o.slug}</p>
                    {o.domain && <p className="text-xs text-ink-soft mt-2">{o.domain}</p>}
                  </div>

                  <div className="mt-5 pt-3 border-t border-line flex items-center justify-between text-xs font-medium text-accent-ink">
                    <span>{o.is_current ? "Active Workspace" : "Switch to Workspace"}</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-6 border-t border-line text-center flex items-center justify-center gap-4 text-xs">
              <button
                onClick={() => setViewMode("create")}
                className="text-ink-soft hover:text-ink font-medium transition-colors"
              >
                + Create Another Organisation
              </button>
              <span className="text-line-strong">|</span>
              <button
                onClick={() => {
                  setValidatedInvite(null);
                  setInviteCode("");
                  setViewMode("join");
                }}
                className="text-ink-soft hover:text-ink font-medium transition-colors"
              >
                Join with an Invitation Code
              </button>
            </div>
          </div>
        )}

        {/* VIEW 2: THE TWO CLEAR CHOICES (CARD A vs CARD B) */}
        {viewMode === "options" && (
          <div className="space-y-8">
            <div className="text-center max-w-lg mx-auto">
              <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-ink border border-accent/30 mb-3">
                <Sparkles className="w-3.5 h-3.5" /> Workspace Setup
              </span>
              <h1 className="text-3xl font-serif font-medium text-ink tracking-tight">
                Welcome to BrandProof
              </h1>
              <p className="text-sm text-ink-soft mt-2">
                BrandProof isolates compliance rules, approved facts, and content reviews by organisation.
                How would you like to get started?
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
              {/* OPTION A: CREATE A NEW ORGANISATION */}
              <div
                onClick={() => setViewMode("create")}
                className="group relative rounded-2xl border-2 border-line bg-surface p-7 transition-all hover:border-accent hover:shadow-xl cursor-pointer flex flex-col justify-between"
              >
                <div className="space-y-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent-soft text-accent-ink border border-accent/20 group-hover:scale-105 transition-transform">
                    <Building2 className="w-6 h-6" />
                  </div>

                  <div>
                    <span className="text-[11px] font-semibold text-accent-ink uppercase tracking-wider">
                      Option A
                    </span>
                    <h2 className="text-xl font-serif font-medium text-ink mt-0.5 group-hover:text-accent-ink transition-colors">
                      Create a New Organisation
                    </h2>
                  </div>

                  <p className="text-xs text-ink-soft leading-relaxed">
                    Create an organisation for your company or brand and invite your team. You will be assigned as
                    the <strong>Owner</strong> with full administrative authority over compliance guidelines,
                    approved facts, and member invitations.
                  </p>

                  <div className="space-y-2 pt-2 text-xs text-ink">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Dedicated, fully isolated brand workspace</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Assign roles and generate invitation codes</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Configure brand guidelines, rules & fact repositories</span>
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-line flex items-center justify-between">
                  <span className="text-xs font-semibold text-accent-ink">Create Organisation</span>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-accent-ink group-hover:bg-accent group-hover:text-ink transition-colors">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </div>
              </div>

              {/* OPTION B: JOIN AN EXISTING ORGANISATION */}
              <div
                onClick={() => setViewMode("join")}
                className="group relative rounded-2xl border-2 border-line bg-surface p-7 transition-all hover:border-accent hover:shadow-xl cursor-pointer flex flex-col justify-between"
              >
                <div className="space-y-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sunken text-accent-ink border border-line group-hover:scale-105 transition-transform">
                    <KeyRound className="w-6 h-6" />
                  </div>

                  <div>
                    <span className="text-[11px] font-semibold text-ink-soft uppercase tracking-wider">
                      Option B
                    </span>
                    <h2 className="text-xl font-serif font-medium text-ink mt-0.5 group-hover:text-accent-ink transition-colors">
                      Join an Existing Organisation
                    </h2>
                  </div>

                  <p className="text-xs text-ink-soft leading-relaxed">
                    Already part of a company using BrandProof? Join your team using an invitation code or link.
                    No need to create an organisation—connect straight to your company&apos;s active workspace.
                  </p>

                  <div className="space-y-2 pt-2 text-xs text-ink">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Enter with code format (e.g. <code>BP-XXXX-XXXX</code>)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Safe organisation preview before joining</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>Instant access or admin approval based on invitation</span>
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-line flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink-soft group-hover:text-accent-ink transition-colors">
                    Enter Invitation Code
                  </span>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sunken text-ink-soft group-hover:bg-accent group-hover:text-ink transition-colors">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 3: OPTION A FORM - CREATE ORGANISATION */}
        {viewMode === "create" && (
          <div className="max-w-md mx-auto space-y-6">
            <button
              onClick={() => setViewMode(myOrgs.length > 0 ? "select" : "options")}
              className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-ink font-medium"
            >
              &larr; Back to choices
            </button>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <Building2 className="w-5 h-5 text-accent-ink" />
                <h1 className="text-2xl font-serif font-medium text-ink">Create an Organisation</h1>
              </div>
              <p className="text-xs text-ink-soft">
                Establish a new brand governance workspace. You will be assigned the <strong>Owner</strong> role.
              </p>
            </div>

            <form onSubmit={handleCreateOrg} className="space-y-4 rounded-xl border border-line bg-surface p-6 shadow-sm">
              <div>
                <label className="block text-xs font-medium text-ink">
                  Organisation Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Acme Global, Nova Brands"
                  value={createName}
                  onChange={(e) => {
                    setCreateName(e.target.value);
                    if (!createSlug) {
                      setCreateSlug(
                        e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]/g, "-")
                          .replace(/-+/g, "-")
                          .replace(/^-|-$/g, "")
                      );
                    }
                  }}
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-ink">
                  Workspace Slug <span className="text-ink-mute">(URL identifier)</span>
                </label>
                <input
                  type="text"
                  placeholder="acme-global"
                  value={createSlug}
                  onChange={(e) => setCreateSlug(e.target.value)}
                  className={inputClass}
                />
                <p className="text-[11px] text-ink-mute mt-1">brandproof.app/{createSlug || "slug"}</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-ink">
                  Corporate Domain <span className="text-ink-mute">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="company.com"
                  value={createDomain}
                  onChange={(e) => setCreateDomain(e.target.value)}
                  className={inputClass}
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  disabled={isCreating}
                  className="w-full flex items-center justify-center gap-2"
                >
                  {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Building2 className="w-4 h-4" />}
                  {isCreating ? "Creating Workspace…" : "Create Organisation & Continue"}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* VIEW 4: OPTION B FORM - JOIN WITH INVITATION CODE */}
        {viewMode === "join" && (
          <div className="max-w-lg mx-auto space-y-6">
            <button
              onClick={() => setViewMode(myOrgs.length > 0 ? "select" : "options")}
              className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-ink font-medium"
            >
              &larr; Back to choices
            </button>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <KeyRound className="w-5 h-5 text-accent-ink" />
                <h1 className="text-2xl font-serif font-medium text-ink">Join an Organisation</h1>
              </div>
              <p className="text-xs text-ink-soft">
                Enter an invitation code or token provided by your organisation administrator.
              </p>
            </div>

            {/* Input & Validation Form */}
            <div className="rounded-xl border border-line bg-surface p-6 shadow-sm space-y-5">
              <div>
                <label className="block text-xs font-medium text-ink">
                  Invitation Code or Token <span className="text-red-500">*</span>
                </label>
                <div className="mt-1.5 flex gap-2">
                  <input
                    type="text"
                    required
                    placeholder="e.g. BP-8K2M-9P4W or raw token"
                    value={inviteCode}
                    onChange={(e) => {
                      setInviteCode(e.target.value);
                      setValidatedInvite(null);
                      setJoinSuccessState(null);
                    }}
                    className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink font-mono placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 uppercase"
                  />
                  <Button
                    type="button"
                    onClick={() => validateCode(inviteCode)}
                    disabled={isValidatingCode || !inviteCode.trim()}
                    className="shrink-0 text-xs flex items-center gap-1.5"
                  >
                    {isValidatingCode && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Validate
                  </Button>
                </div>
                <p className="text-[11px] text-ink-mute mt-1">
                  Format: <code>BP-XXXX-XXXX</code> or cryptographic invite token.
                </p>
              </div>

              {/* SAFE ORGANISATION PREVIEW */}
              {validatedInvite && !joinSuccessState && (
                <div className="rounded-xl border border-accent/40 bg-accent-soft/30 p-5 space-y-4 animate-in fade-in duration-200">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      {validatedInvite.logo_url ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img
                          src={validatedInvite.logo_url}
                          alt={validatedInvite.organization_name}
                          className="w-10 h-10 rounded-lg object-contain bg-white border border-line"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-surface border border-accent/30 flex items-center justify-center text-accent-ink font-bold text-sm">
                          {validatedInvite.organization_name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <h3 className="font-serif font-medium text-base text-ink">
                          {validatedInvite.organization_name}
                        </h3>
                        <p className="text-[11px] text-ink-mute font-mono">/{validatedInvite.organization_slug}</p>
                      </div>
                    </div>

                    <span className="inline-flex items-center gap-1 rounded bg-emerald-100 text-emerald-800 px-2 py-0.5 text-[11px] font-semibold">
                      <Check className="w-3 h-3" /> Valid Code
                    </span>
                  </div>

                  {validatedInvite.description && (
                    <p className="text-xs text-ink-soft leading-relaxed border-t border-line/60 pt-2">
                      {validatedInvite.description}
                    </p>
                  )}

                  {/* Role Selector / Display */}
                  <div className="border-t border-line/60 pt-3">
                    <label className="block text-xs font-medium text-ink mb-1.5">
                      Assigned Role:
                    </label>
                    {validatedInvite.allowed_roles && validatedInvite.allowed_roles.length > 1 ? (
                      <div className="space-y-1.5">
                        <select
                          value={selectedRole}
                          onChange={(e) => setSelectedRole(e.target.value as UserRole)}
                          className={inputClass}
                        >
                          {validatedInvite.allowed_roles.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                        <p className="text-[11px] text-ink-mute">
                          This invitation permits multiple roles. Please select your position.
                        </p>
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-md bg-surface px-3 py-1.5 text-xs font-semibold text-accent-ink border border-line">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        {selectedRole || validatedInvite.role || "Creator"}
                      </span>
                    )}
                  </div>

                  {/* Approval Requirement Notice */}
                  <div className="border-t border-line/60 pt-3">
                    {validatedInvite.requires_approval ? (
                      <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md p-2.5">
                        <Clock className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                        <div>
                          <strong className="block font-medium">Administrator Approval Required</strong>
                          <span>
                            Upon joining, a membership request will be sent to the organisation admins. You will
                            gain access once approved.
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-md p-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Instant Access: You will immediately join this workspace.</span>
                      </div>
                    )}
                  </div>

                  {/* Join Action Button */}
                  <form onSubmit={handleJoinOrg} className="pt-2">
                    <Button
                      type="submit"
                      disabled={isJoining}
                      className="w-full flex items-center justify-center gap-2"
                    >
                      {isJoining && <Loader2 className="w-4 h-4 animate-spin" />}
                      {validatedInvite.requires_approval
                        ? "Submit Membership Request"
                        : "Join Organisation Now"}
                    </Button>
                  </form>
                </div>
              )}

              {/* SUCCESS / PENDING APPROVAL STATE */}
              {joinSuccessState && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-center space-y-4">
                  <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center mx-auto">
                    <Clock className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-serif font-medium text-lg text-ink">
                      Membership Request Pending
                    </h3>
                    <p className="text-xs text-ink-soft mt-1 max-w-sm mx-auto">
                      {joinSuccessState.message ||
                        `Your request to join ${joinSuccessState.orgName} has been submitted. An administrator will review your application.`}
                    </p>
                  </div>
                  <div className="pt-2 flex justify-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setViewMode(myOrgs.length > 0 ? "select" : "options")}
                    >
                      Return to Workspace Options
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-line py-4 text-center text-xs text-ink-mute">
        BrandProof Enterprise Governance Platform &bull; Data Isolation &amp; Role Integrity Protected
      </footer>
    </div>
  );
}
