"use client";

import React, { useState, useRef, useEffect } from "react";
import { Building2, Check, ChevronDown, Plus, Mail, Loader2, Sparkles } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { cn } from "@/lib/utils";

export function OrgSwitcher() {
  const {
    currentOrganization,
    organizations,
    pendingInvitations,
    switchOrganization,
    createOrganization,
    acceptInvitation,
    user,
  } = useAuth();
  const { success, error } = useToast();

  const [isOpen, setIsOpen] = useState(false);
  const [isSwitchingId, setIsSwitchingId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgSlug, setNewOrgSlug] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [acceptingToken, setAcceptingToken] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setShowCreateModal(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleSwitch = async (orgId: string) => {
    if (orgId === currentOrganization?.id) {
      setIsOpen(false);
      return;
    }
    setIsSwitchingId(orgId);
    try {
      await switchOrganization(orgId);
      setIsOpen(false);
    } catch (err: any) {
      error("Failed to switch organization", err.message || "An error occurred");
    } finally {
      setIsSwitchingId(null);
    }
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    setIsCreating(true);
    try {
      await createOrganization({
        name: newOrgName.trim(),
        slug: newOrgSlug.trim() || undefined,
      });
      success("Organization Created", `Welcome to ${newOrgName.trim()}!`);
      setShowCreateModal(false);
      setNewOrgName("");
      setNewOrgSlug("");
      setIsOpen(false);
    } catch (err: any) {
      error("Failed to create organization", err.message || "An error occurred");
    } finally {
      setIsCreating(false);
    }
  };

  const handleAcceptInvite = async (token: string, orgName?: string) => {
    setAcceptingToken(token);
    try {
      await acceptInvitation(token);
      success("Invitation Accepted", `You have joined ${orgName || "the organization"}!`);
      setIsOpen(false);
    } catch (err: any) {
      error("Failed to accept invitation", err.message || "Invalid or expired token");
    } finally {
      setAcceptingToken(null);
    }
  };

  const activeOrgName = currentOrganization?.name || "Organization";
  const userRoleInOrg = currentOrganization?.is_owner
    ? "Owner"
    : currentOrganization?.role || user?.role || "Member";

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      {/* Switcher Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink transition-colors hover:bg-sunken hover:border-line-strong focus:outline-none"
        aria-expanded={isOpen}
      >
        <Building2 className="w-3.5 h-3.5 text-accent-ink shrink-0" />
        <span className="font-semibold max-w-[140px] truncate">{activeOrgName}</span>
        <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent-ink border border-accent/20">
          {userRoleInOrg}
        </span>
        {pendingInvitations.length > 0 && (
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
          </span>
        )}
        <ChevronDown
          className={cn("w-3 h-3 text-ink-mute transition-transform", isOpen && "rotate-180")}
        />
      </button>

      {/* Switcher Dropdown */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-1.5 w-72 rounded-lg border border-line bg-surface shadow-soft z-50 py-1.5 animate-in fade-in duration-150">
          <div className="px-3 py-1.5 border-b border-line">
            <p className="text-[11px] font-medium text-ink-mute uppercase tracking-wider">
              Organizations ({organizations.length})
            </p>
          </div>

          {/* Org List */}
          <div className="max-h-60 overflow-y-auto py-1">
            {organizations.map((org) => {
              const isActive = org.id === currentOrganization?.id;
              const isSwitching = isSwitchingId === org.id;
              const displayRole = org.is_owner ? "Owner" : org.role;

              return (
                <button
                  key={org.id}
                  onClick={() => handleSwitch(org.id)}
                  disabled={isSwitching}
                  className={cn(
                    "flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors hover:bg-sunken",
                    isActive ? "bg-sunken/60 font-medium text-ink" : "text-ink-soft"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Building2
                      className={cn(
                        "w-3.5 h-3.5 shrink-0",
                        isActive ? "text-accent-ink" : "text-ink-mute"
                      )}
                    />
                    <div className="truncate">
                      <p className="truncate text-ink font-medium">{org.name}</p>
                      <p className="text-[10px] text-ink-mute font-mono truncate">{org.slug}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    <span className="rounded bg-sunken px-1.5 py-0.5 text-[10px] text-ink-soft border border-line">
                      {displayRole}
                    </span>
                    {isSwitching ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-ink" />
                    ) : isActive ? (
                      <Check className="w-3.5 h-3.5 text-accent-ink" />
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Pending Invitations Section */}
          {pendingInvitations.length > 0 && (
            <div className="border-t border-line pt-1">
              <div className="px-3 py-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium text-ink-mute uppercase tracking-wider flex items-center gap-1">
                  <Mail className="w-3 h-3 text-accent-ink" />
                  Invitations ({pendingInvitations.length})
                </span>
              </div>
              <div className="max-h-36 overflow-y-auto py-0.5">
                {pendingInvitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="px-3 py-2 text-xs border-b border-line/40 last:border-b-0 hover:bg-sunken/40 flex items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-ink truncate">
                        {inv.organization_name || "Workspace Invite"}
                      </p>
                      <p className="text-[10px] text-ink-mute">
                        Role: {inv.assigned_role}
                        {inv.inviter_name ? ` · by ${inv.inviter_name}` : ""}
                      </p>
                    </div>
                    {inv.invite_token && (
                      <button
                        type="button"
                        onClick={() => handleAcceptInvite(inv.invite_token!, inv.organization_name)}
                        disabled={acceptingToken === inv.invite_token}
                        className="rounded bg-accent px-2 py-1 text-[11px] font-medium text-ink hover:bg-accent-hover transition-colors shrink-0 disabled:opacity-50 flex items-center gap-1"
                      >
                        {acceptingToken === inv.invite_token ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          "Accept"
                        )}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bottom Actions: Create Org */}
          <div className="border-t border-line pt-1">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setShowCreateModal(true);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-accent-ink hover:bg-sunken transition-colors font-medium"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create New Organization</span>
            </button>
          </div>
        </div>
      )}

      {/* Create Organization Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-2xl">
            <div className="flex items-center gap-2 mb-1">
              <Building2 className="w-5 h-5 text-accent-ink" />
              <h2 className="text-lg font-serif font-medium text-ink">Create Organization</h2>
            </div>
            <p className="text-xs text-ink-soft mb-4">
              Add a new organization workspace under your global account. You will be set as the Owner.
            </p>

            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-ink">Organization Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Apex Health Brands"
                  value={newOrgName}
                  onChange={(e) => {
                    setNewOrgName(e.target.value);
                    if (!newOrgSlug) {
                      setNewOrgSlug(
                        e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]+/g, "-")
                          .replace(/(^-|-$)/g, "")
                      );
                    }
                  }}
                  className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-ink">
                  Workspace Slug <span className="text-ink-mute">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="apex-health-brands"
                  value={newOrgSlug}
                  onChange={(e) => setNewOrgSlug(e.target.value.toLowerCase())}
                  className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink font-mono placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                />
                <p className="text-[11px] text-ink-mute mt-1">
                  Unique identifier used in references and URLs.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-md px-3.5 py-1.5 text-xs text-ink-soft hover:bg-sunken transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newOrgName.trim()}
                  className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-accent-hover disabled:opacity-50"
                >
                  {isCreating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {isCreating ? "Creating Workspace…" : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
