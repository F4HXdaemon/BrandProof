"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Building2,
  Users,
  Shield,
  UserPlus,
  Trash2,
  Copy,
  Check,
  Crown,
  Mail,
  Clock,
  AlertTriangle,
  Loader2,
  ArrowRightLeft,
  X,
  KeyRound,
  CheckCircle2,
  Compass,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductTourModal } from "@/components/onboarding/product-tour-modal";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import {
  Organization,
  OrganizationMembership,
  OrganizationInvitation,
  UserRole,
} from "@/lib/types";

const ASSIGNABLE_ROLES: UserRole[] = [
  "Admin",
  "Brand Manager",
  "Fact Owner",
  "Reviewer",
  "Creator",
];

const ROLES_MATRIX = [
  {
    role: "Owner",
    access: "Full organization ownership, member & role management, billing, and ownership transfer.",
  },
  {
    role: "Admin",
    access: "Manage members, configure organization settings, invite users, and audit workspace security.",
  },
  {
    role: "Brand Manager",
    access: "Create & update guidelines, approved terminology, and governance rules. Supervise review blockers.",
  },
  {
    role: "Fact Owner",
    access: "Authoritative registration and lifecycle maintenance of verified facts & source evidence citations.",
  },
  {
    role: "Reviewer",
    access: "Inspect drafts, verify citations, and issue human approvals or change requests. Cannot override blockers.",
  },
  {
    role: "Creator",
    access: "Upload draft marketing copy, inspect automated claim findings, and submit revisions.",
  },
];

export default function SettingsPage() {
  const { user, currentOrganization, refreshOrganizations } = useAuth();
  const { success, error } = useToast();

  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMembership[]>([]);
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);
  const [membershipRequests, setMembershipRequests] = useState<OrganizationMembership[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTour, setShowTour] = useState(false);

  // Invite modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("Reviewer");
  const [inviteAllowedRoles, setInviteAllowedRoles] = useState<UserRole[]>(["Reviewer"]);
  const [inviteExpiresDays, setInviteExpiresDays] = useState(7);
  const [inviteMaxUses, setInviteMaxUses] = useState(1);
  const [inviteRequiresApproval, setInviteRequiresApproval] = useState(false);
  const [isInviting, setIsInviting] = useState(false);
  const [generatedInviteUrl, setGeneratedInviteUrl] = useState<string | null>(null);
  const [generatedInviteCode, setGeneratedInviteCode] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  // Transfer ownership modal state
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [newOwnerUserId, setNewOwnerUserId] = useState("");
  const [isTransferring, setIsTransferring] = useState(false);

  // Action states
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [revokingInviteId, setRevokingInviteId] = useState<string | null>(null);
  const [processingRequestId, setProcessingRequestId] = useState<string | null>(null);

  const isOwner =
    currentOrganization?.is_owner ||
    user?.role === "Owner" ||
    (org?.owner_id && org.owner_id === user?.id);

  const isAdminOrOwner = isOwner || user?.role === "Admin";

  const loadData = useCallback(async () => {
    try {
      const [orgData, membersData] = await Promise.all([
        api.organizations.getCurrent(),
        api.organizations.getMembers(),
      ]);
      setOrg(orgData);
      setMembers(membersData);

      const canManageInvites =
        currentOrganization?.is_owner ||
        user?.role === "Owner" ||
        user?.role === "Admin" ||
        (orgData?.owner_id && orgData.owner_id === user?.id);

      if (canManageInvites) {
        try {
          const [invData, reqData] = await Promise.all([
            api.organizations.getPendingInvitations(),
            api.organizations.getMembershipRequests().catch(() => []),
          ]);
          setInvitations(invData);
          setMembershipRequests(reqData);
        } catch {
          // Non-admin may not have access to invites
        }
      }
    } catch (err: any) {
      console.error(err);
      error("Error loading settings", err.message || "Failed to load organization data");
    } finally {
      setLoading(false);
    }
  }, [currentOrganization?.is_owner, user?.role, user?.id, error]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRoleChange = async (membershipId: string, newRole: UserRole) => {
    setUpdatingMemberId(membershipId);
    try {
      await api.organizations.updateMemberRole(membershipId, newRole);
      success("Role Updated", `Member role updated to ${newRole}`);
      await loadData();
    } catch (err: any) {
      error("Failed to update role", err.message || "An error occurred");
    } finally {
      setUpdatingMemberId(null);
    }
  };

  const handleRemoveMember = async (membership: OrganizationMembership) => {
    if (membership.is_owner) {
      error("Cannot Remove Owner", "The organization owner cannot be removed. Transfer ownership first.");
      return;
    }
    if (membership.user_id === user?.id) {
      error("Cannot Remove Yourself", "You cannot remove your own membership here.");
      return;
    }
    if (!window.confirm(`Are you sure you want to remove ${membership.full_name} (${membership.email}) from this organization?`)) {
      return;
    }

    try {
      await api.organizations.removeMember(membership.id);
      success("Member Removed", `${membership.full_name} has been removed from the organization.`);
      await loadData();
    } catch (err: any) {
      error("Failed to remove member", err.message || "An error occurred");
    }
  };

  const handleApproveRequest = async (requestId: string, role?: UserRole) => {
    setProcessingRequestId(requestId);
    try {
      await api.organizations.approveMembershipRequest(requestId, role ? { role } : undefined);
      success("Membership Approved", "The applicant has been granted access to the workspace.");
      await loadData();
    } catch (err: any) {
      error("Approval Failed", err.message || "Could not approve membership request.");
    } finally {
      setProcessingRequestId(null);
    }
  };

  const handleRejectRequest = async (requestId: string) => {
    if (!window.confirm("Are you sure you want to reject this membership request?")) return;
    setProcessingRequestId(requestId);
    try {
      await api.organizations.rejectMembershipRequest(requestId);
      success("Request Dismissed", "The membership request has been removed.");
      await loadData();
    } catch (err: any) {
      error("Rejection Failed", err.message || "Could not reject membership request.");
    } finally {
      setProcessingRequestId(null);
    }
  };

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInviting(true);
    try {
      const res = await api.organizations.createInvitation({
        email: inviteEmail.trim() || undefined,
        role: inviteRole,
        allowed_roles: inviteAllowedRoles.length > 0 ? inviteAllowedRoles : [inviteRole],
        expires_in_days: inviteExpiresDays,
        max_uses: inviteMaxUses,
        requires_approval: inviteRequiresApproval,
      });

      const fullUrl =
        res.invite_url ||
        `${window.location.origin}/invite/${res.invite_token}`;
      setGeneratedInviteUrl(fullUrl);
      setGeneratedInviteCode(res.invitation_code || null);
      success("Invitation Generated", "Invitation code created successfully.");
      await loadData();
    } catch (err: any) {
      error("Failed to invite member", err.message || "An error occurred");
    } finally {
      setIsInviting(false);
    }
  };

  const handleRevokeInvite = async (inviteId: string) => {
    if (!window.confirm("Are you sure you want to revoke this invitation?")) return;
    setRevokingInviteId(inviteId);
    try {
      await api.organizations.revokeInvitation(inviteId);
      success("Invitation Revoked", "The invitation has been cancelled.");
      await loadData();
    } catch (err: any) {
      error("Failed to revoke invitation", err.message || "An error occurred");
    } finally {
      setRevokingInviteId(null);
    }
  };

  const handleTransferOwnership = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOwnerUserId) return;
    const targetMember = members.find((m) => m.user_id === newOwnerUserId);
    if (!targetMember) return;

    if (
      !window.confirm(
        `Are you sure you want to transfer ownership of ${org?.name} to ${targetMember.full_name} (${targetMember.email})? You will step down to Admin.`
      )
    ) {
      return;
    }

    setIsTransferring(true);
    try {
      await api.organizations.transferOwnership(newOwnerUserId);
      success("Ownership Transferred", `Ownership transferred to ${targetMember.full_name}.`);
      setShowTransferModal(false);
      await refreshOrganizations();
      await loadData();
    } catch (err: any) {
      error("Transfer failed", err.message || "An error occurred");
    } finally {
      setIsTransferring(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const copyCodeToClipboard = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl mx-auto pb-12">
        <div>
          <h1 className="page-title text-3xl text-ink">Organization Settings</h1>
          <p className="text-xs text-ink-soft mt-1">
            Manage your organization profile, team members, roles, and invitation security.
          </p>
        </div>

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Organization Profile */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Organization Profile</CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="status" value={org?.is_active ? "Active" : "Suspended"} />
                  {isOwner && (
                    <button
                      onClick={() => setShowTransferModal(true)}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-accent-ink hover:underline"
                    >
                      <ArrowRightLeft className="w-3 h-3" />
                      Transfer Ownership
                    </button>
                  )}
                </div>
              </CardHeader>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs pt-1">
                <div>
                  <span className="text-ink-mute block">Organization Name</span>
                  <span className="font-semibold text-ink mt-0.5 block">{org?.name}</span>
                </div>
                <div>
                  <span className="text-ink-mute block">Workspace Slug</span>
                  <span className="font-mono text-accent-ink mt-0.5 block">{org?.slug}</span>
                </div>
                <div>
                  <span className="text-ink-mute block">Corporate Domain</span>
                  <span className="text-ink mt-0.5 block">{org?.domain || "—"}</span>
                </div>
                <div>
                  <span className="text-ink-mute block">Organization Owner</span>
                  <div className="flex items-center gap-1 mt-0.5">
                    <Crown className="w-3 h-3 text-accent-ink" />
                    <span className="font-medium text-ink">
                      {members.find((m) => m.is_owner)?.full_name || "Owner Assigned"}
                    </span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Product Guidance & First-Time Tour */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <Compass className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Product Tour & Guidance</CardTitle>
                </div>
                <Badge variant="status" value={user?.onboarding_completed ? "Approved" : "In Progress"} />
              </CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
                <p className="text-xs text-ink-soft max-w-xl">
                  Revisit the 5-step interactive walkthrough detailing brand knowledge management,
                  CitationGate verification, and audit report generation.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowTour(true)}
                  className="bg-surface border-line-strong hover:bg-sunken text-ink text-xs shrink-0"
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1.5 text-accent" />
                  <span>Replay Product Tour</span>
                </Button>
              </div>
            </Card>

            {/* Pending Membership Requests (Admin / Owner view) */}
            {isAdminOrOwner && membershipRequests.length > 0 && (
              <Card className="border-amber-300 bg-amber-50/40">
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-amber-700" />
                    <CardTitle className="text-amber-950">
                      Pending Membership Requests ({membershipRequests.length})
                    </CardTitle>
                  </div>
                  <span className="rounded-full bg-amber-200/80 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900 border border-amber-300">
                    Action Required
                  </span>
                </CardHeader>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-amber-200 text-amber-900 font-medium">
                        <th className="pb-2.5">Applicant</th>
                        <th className="pb-2.5">Email</th>
                        <th className="pb-2.5">Requested Role</th>
                        <th className="pb-2.5">Submitted</th>
                        <th className="pb-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-amber-200/60">
                      {membershipRequests.map((req) => (
                        <tr key={req.id} className="hover:bg-amber-100/50 transition-colors">
                          <td className="py-2.5">
                            <span className="font-medium text-ink block">{req.full_name}</span>
                          </td>
                          <td className="py-2.5 font-mono text-[11px] text-ink-soft">{req.email}</td>
                          <td className="py-2.5">
                            <span className="px-2 py-0.5 rounded bg-surface text-accent-ink font-semibold text-[11px] border border-line">
                              {req.role}
                            </span>
                          </td>
                          <td className="py-2.5 text-ink-soft text-[11px]">
                            {req.joined_at ? new Date(req.joined_at).toLocaleDateString() : "Just now"}
                          </td>
                          <td className="py-2.5 text-right space-x-2">
                            <Button
                              size="sm"
                              onClick={() => handleApproveRequest(req.id, req.role)}
                              disabled={processingRequestId === req.id}
                              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                            >
                              {processingRequestId === req.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Check className="w-3 h-3 mr-1" />
                              )}
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleRejectRequest(req.id)}
                              disabled={processingRequestId === req.id}
                              className="text-xs"
                            >
                              Reject
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* Team Members List */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Team Members ({members.length})</CardTitle>
                </div>
                {isAdminOrOwner && (
                  <Button
                    size="sm"
                    onClick={() => {
                      setGeneratedInviteUrl(null);
                      setGeneratedInviteCode(null);
                      setInviteEmail("");
                      setInviteRole("Reviewer");
                      setInviteAllowedRoles(["Reviewer"]);
                      setInviteMaxUses(1);
                      setInviteRequiresApproval(false);
                      setShowInviteModal(true);
                    }}
                    className="flex items-center gap-1.5 text-xs"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    Generate Invitation Code
                  </Button>
                )}
              </CardHeader>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-ink-soft font-medium">
                      <th className="pb-2.5">Member</th>
                      <th className="pb-2.5">Email</th>
                      <th className="pb-2.5">Role</th>
                      <th className="pb-2.5">Joined</th>
                      <th className="pb-2.5">Status</th>
                      {isAdminOrOwner && <th className="pb-2.5 text-right">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {members.map((m) => {
                      const isMemberOwner = m.is_owner;
                      const isSelf = m.user_id === user?.id;
                      const canModify = isAdminOrOwner && !isMemberOwner && (!isSelf || isOwner);

                      return (
                        <tr key={m.id} className="hover:bg-sunken/60 transition-colors">
                          <td className="py-2.5">
                            <div className="flex items-center gap-2">
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent-soft text-[10px] font-semibold text-accent-ink">
                                {m.full_name?.charAt(0) || "U"}
                              </span>
                              <div>
                                <span className="font-medium text-ink block">{m.full_name}</span>
                                {m.title && (
                                  <span className="text-[10px] text-ink-mute block">{m.title}</span>
                                )}
                              </div>
                              {isMemberOwner && (
                                <span className="inline-flex items-center gap-0.5 rounded bg-accent-soft px-1.5 py-0.2 text-[10px] font-semibold text-accent-ink border border-accent/20">
                                  <Crown className="w-2.5 h-2.5" />
                                  Owner
                                </span>
                              )}
                              {isSelf && (
                                <span className="text-[10px] text-ink-mute">(You)</span>
                              )}
                            </div>
                          </td>

                          <td className="py-2.5 text-ink-soft font-mono text-[11px]">{m.email}</td>

                          <td className="py-2.5">
                            {canModify ? (
                              <select
                                value={m.role}
                                onChange={(e) =>
                                  handleRoleChange(m.id, e.target.value as UserRole)
                                }
                                disabled={updatingMemberId === m.id}
                                className="rounded border border-line bg-surface px-2 py-1 text-xs text-ink focus:outline-none focus:border-accent"
                              >
                                {ASSIGNABLE_ROLES.map((r) => (
                                  <option key={r} value={r}>
                                    {r}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-sunken text-accent-ink font-medium text-[11px] border border-line-strong">
                                {isMemberOwner ? "Owner" : m.role}
                              </span>
                            )}
                          </td>

                          <td className="py-2.5 text-ink-soft text-[11px]">
                            {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—"}
                          </td>

                          <td className="py-2.5">
                            <Badge
                              variant="status"
                              value={m.status === "active" ? "Active" : m.status}
                            />
                          </td>

                          {isAdminOrOwner && (
                            <td className="py-2.5 text-right">
                              {canModify && !isSelf && (
                                <button
                                  type="button"
                                  onClick={() => handleRemoveMember(m)}
                                  className="text-ink-mute hover:text-red-500 transition-colors p-1"
                                  title="Remove member"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Invitations & Codes (Admin / Owner view) */}
            {isAdminOrOwner && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div className="flex items-center gap-2">
                    <KeyRound className="w-4 h-4 text-accent-ink" />
                    <CardTitle>Organisation Invitations &amp; Codes ({invitations.length})</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Cryptographic invitation tokens and shareable codes for onboarding team members.
                  </CardDescription>
                </CardHeader>

                {invitations.length === 0 ? (
                  <p className="text-xs text-ink-mute py-4 text-center">
                    No active invitations. Click &quot;Generate Invitation Code&quot; to issue an invite.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-line text-ink-soft font-medium">
                          <th className="pb-2.5">Invitation Code</th>
                          <th className="pb-2.5">Recipient</th>
                          <th className="pb-2.5">Permitted Roles</th>
                          <th className="pb-2.5">Usage</th>
                          <th className="pb-2.5">Policy</th>
                          <th className="pb-2.5">Expires</th>
                          <th className="pb-2.5 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {invitations.map((inv) => (
                          <tr key={inv.id} className="hover:bg-sunken/60 transition-colors">
                            <td className="py-2.5 font-mono text-[11px] font-semibold text-accent-ink">
                              {inv.invitation_code ? (
                                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface border border-accent/20">
                                  {inv.invitation_code}
                                  <button
                                    type="button"
                                    onClick={() => copyCodeToClipboard(inv.invitation_code!)}
                                    className="text-ink-mute hover:text-ink"
                                    title="Copy Code"
                                  >
                                    <Copy className="w-3 h-3" />
                                  </button>
                                </span>
                              ) : (
                                <span className="text-ink-mute italic">Direct Token</span>
                              )}
                            </td>
                            <td className="py-2.5 font-mono text-[11px] text-ink">
                              {inv.invited_email || (
                                <span className="text-ink-mute italic">Anyone with code</span>
                              )}
                            </td>
                            <td className="py-2.5">
                              <span className="px-2 py-0.5 rounded bg-sunken text-accent-ink font-medium text-[11px] border border-line-strong">
                                {inv.allowed_roles && inv.allowed_roles.length > 0
                                  ? inv.allowed_roles.join(", ")
                                  : inv.assigned_role}
                              </span>
                            </td>
                            <td className="py-2.5 text-ink-soft text-[11px]">
                              {inv.use_count ?? 0} / {inv.max_uses === 0 ? "Unlimited" : (inv.max_uses ?? 1)}
                            </td>
                            <td className="py-2.5">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  inv.requires_approval
                                    ? "bg-amber-100 text-amber-800 border border-amber-200"
                                    : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                }`}
                              >
                                {inv.requires_approval ? "Approval Required" : "Instant Join"}
                              </span>
                            </td>
                            <td className="py-2.5 text-ink-soft text-[11px]">
                              {inv.expires_at
                                ? new Date(inv.expires_at).toLocaleDateString()
                                : "—"}
                            </td>
                            <td className="py-2.5 text-right space-x-2">
                              {inv.invite_token && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    copyToClipboard(
                                      inv.invite_url ||
                                        `${window.location.origin}/invite/${inv.invite_token}`
                                    )
                                  }
                                  className="inline-flex items-center gap-1 text-[11px] text-ink-soft hover:text-ink transition-colors"
                                  title="Copy invite URL"
                                >
                                  <Copy className="w-3 h-3" />
                                  Link
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleRevokeInvite(inv.id)}
                                disabled={revokingInviteId === inv.id}
                                className="inline-flex items-center gap-1 text-[11px] text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                                title="Revoke invitation"
                              >
                                {revokingInviteId === inv.id ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Trash2 className="w-3 h-3" />
                                )}
                                Revoke
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            )}

            {/* Role-Based Access Control (RBAC) Matrix */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Role-Based Access Control (RBAC) Hierarchy</CardTitle>
                </div>
                <CardDescription className="text-xs">
                  Permissions are scoped per organization membership. Role in one workspace does
                  not grant access in another.
                </CardDescription>
              </CardHeader>

              <div className="divide-y divide-line text-xs">
                {ROLES_MATRIX.map((item) => {
                  const isCurrentRole =
                    (isOwner && item.role === "Owner") ||
                    (!isOwner && user?.role === item.role);

                  return (
                    <div
                      key={item.role}
                      className="py-2.5 flex items-start justify-between gap-4"
                    >
                      <div className="space-y-0.5">
                        <span className="font-semibold text-ink">{item.role}</span>
                        <p className="text-ink-soft">{item.access}</p>
                      </div>
                      {isCurrentRole && (
                        <span className="px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20 font-semibold text-[11px] shrink-0">
                          Your Active Role
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        )}

        {/* Invite Member / Generate Invitation Code Modal */}
        {showInviteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-2xl relative">
              <button
                onClick={() => setShowInviteModal(false)}
                className="absolute top-4 right-4 text-ink-mute hover:text-ink"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-2 mb-1">
                <KeyRound className="w-5 h-5 text-accent-ink" />
                <h2 className="text-lg font-serif font-medium text-ink">Generate Invitation Code</h2>
              </div>
              <p className="text-xs text-ink-soft mb-4">
                Create a secure invitation code or shareable link to invite team members into <strong>{org?.name}</strong>.
              </p>

              {!generatedInviteUrl && !generatedInviteCode ? (
                <form onSubmit={handleCreateInvite} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-ink">
                      Invitee Email Address <span className="text-ink-mute">(optional)</span>
                    </label>
                    <input
                      type="email"
                      placeholder="teammate@company.com (leave empty for shareable code)"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                    />
                    <p className="text-[11px] text-ink-mute mt-1">
                      If specified, only an account with this exact email can accept the invitation.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-ink">Default Assigned Role *</label>
                      <select
                        value={inviteRole}
                        onChange={(e) => {
                          const r = e.target.value as UserRole;
                          setInviteRole(r);
                          setInviteAllowedRoles([r]);
                        }}
                        className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                      >
                        {ASSIGNABLE_ROLES.filter((r) => isOwner || r !== "Admin").map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink">Expiration *</label>
                      <select
                        value={inviteExpiresDays}
                        onChange={(e) => setInviteExpiresDays(Number(e.target.value))}
                        className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                      >
                        <option value={1}>1 Day</option>
                        <option value={7}>7 Days (Standard)</option>
                        <option value={14}>14 Days</option>
                        <option value={30}>30 Days</option>
                        <option value={90}>90 Days</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-ink">Maximum Uses (Acceptance Limit) *</label>
                    <select
                      value={inviteMaxUses}
                      onChange={(e) => setInviteMaxUses(Number(e.target.value))}
                      className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                    >
                      <option value={1}>Single-use (1 successful join)</option>
                      <option value={5}>Limited to 5 joins</option>
                      <option value={10}>Limited to 10 joins</option>
                      <option value={25}>Limited to 25 joins</option>
                      <option value={0}>Unlimited joins</option>
                    </select>
                  </div>

                  <div className="pt-1">
                    <label className="flex items-start gap-2.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={inviteRequiresApproval}
                        onChange={(e) => setInviteRequiresApproval(e.target.checked)}
                        className="mt-0.5 rounded border-line-strong text-accent focus:ring-accent"
                      />
                      <div>
                        <span className="text-xs font-medium text-ink block">
                          Require Administrator Approval
                        </span>
                        <span className="text-[11px] text-ink-mute block">
                          When checked, users entering this code submit a membership request instead of joining instantly.
                        </span>
                      </div>
                    </label>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-4 border-t border-line">
                    <button
                      type="button"
                      onClick={() => setShowInviteModal(false)}
                      className="rounded-md px-3.5 py-1.5 text-xs text-ink-soft hover:bg-sunken transition-colors"
                    >
                      Cancel
                    </button>
                    <Button
                      type="submit"
                      disabled={isInviting}
                      className="flex items-center gap-1.5 text-xs"
                    >
                      {isInviting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      Generate Invitation Code
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-lg border border-accent/30 bg-accent-soft p-3.5 text-xs text-ink space-y-1">
                    <p className="font-semibold text-accent-ink">Invitation Generated Successfully</p>
                    <p className="text-ink-soft">
                      Share the invitation code or link below. Users joining will receive the role{" "}
                      <strong>{inviteRole}</strong>.
                    </p>
                  </div>

                  {generatedInviteCode && (
                    <div>
                      <label className="block text-xs font-medium text-ink">Invitation Code</label>
                      <div className="mt-1.5 flex items-center gap-2">
                        <input
                          type="text"
                          readOnly
                          value={generatedInviteCode}
                          className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm font-mono font-bold text-accent-ink tracking-wider focus:outline-none"
                        />
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => copyCodeToClipboard(generatedInviteCode)}
                          className="shrink-0 flex items-center gap-1 text-xs"
                        >
                          {copiedCode ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          {copiedCode ? "Copied" : "Copy Code"}
                        </Button>
                      </div>
                    </div>
                  )}

                  {generatedInviteUrl && (
                    <div>
                      <label className="block text-xs font-medium text-ink">Direct Invitation Link</label>
                      <div className="mt-1.5 flex items-center gap-2">
                        <input
                          type="text"
                          readOnly
                          value={generatedInviteUrl}
                          className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-xs text-ink font-mono focus:outline-none"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(generatedInviteUrl)}
                          className="shrink-0 flex items-center gap-1 text-xs"
                        >
                          {copiedLink ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          {copiedLink ? "Copied" : "Copy Link"}
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-end pt-3 border-t border-line">
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      onClick={() => setShowInviteModal(false)}
                    >
                      Done
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Transfer Ownership Modal */}
        {showTransferModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-2xl relative">
              <button
                onClick={() => setShowTransferModal(false)}
                className="absolute top-4 right-4 text-ink-mute hover:text-ink"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-2 mb-1">
                <Crown className="w-5 h-5 text-accent-ink" />
                <h2 className="text-lg font-serif font-medium text-ink">Transfer Organization Ownership</h2>
              </div>
              <p className="text-xs text-ink-soft mb-4">
                Select an active team member to become the new Owner of <strong>{org?.name}</strong>.
                You will retain Admin access.
              </p>

              <form onSubmit={handleTransferOwnership} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-ink">New Owner *</label>
                  <select
                    required
                    value={newOwnerUserId}
                    onChange={(e) => setNewOwnerUserId(e.target.value)}
                    className="mt-1.5 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
                  >
                    <option value="">Select a member...</option>
                    {members
                      .filter((m) => !m.is_owner && m.user_id !== user?.id)
                      .map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.full_name} ({m.email}) - {m.role}
                        </option>
                      ))}
                  </select>
                </div>

                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-600 space-y-1">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>Irreversible Action</span>
                  </div>
                  <p className="text-[11px] opacity-90">
                    Once ownership is transferred, only the new owner will have authority to transfer
                    it again or delete the organization.
                  </p>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-line">
                  <button
                    type="button"
                    onClick={() => setShowTransferModal(false)}
                    className="rounded-md px-3.5 py-1.5 text-xs text-ink-soft hover:bg-sunken transition-colors"
                  >
                    Cancel
                  </button>
                  <Button
                    type="submit"
                    disabled={isTransferring || !newOwnerUserId}
                    className="flex items-center gap-1.5 text-xs bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                  >
                    {isTransferring && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Confirm Transfer
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        <ProductTourModal
          isOpen={showTour}
          onClose={() => setShowTour(false)}
          onComplete={() => {
            setShowTour(false);
            success("Product Tour", "Tour walkthrough completed.");
          }}
        />
      </div>
    </AppShell>
  );
}
