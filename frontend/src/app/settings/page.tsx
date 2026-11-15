"use client";

import React, { useEffect, useState } from "react";
import { Settings, Building2, Users, Shield, Lock, CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { api } from "@/lib/api";
import { Organization, User } from "@/lib/types";

export default function SettingsPage() {
  const { user } = useAuth();
  const { success, error } = useToast();

  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [orgData, membersData] = await Promise.all([
          api.organizations.getCurrent(),
          api.organizations.getMembers(),
        ]);
        setOrg(orgData);
        setMembers(membersData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const rolesMatrix = [
    { role: "Admin", access: "Full organization access, user management, and security policies." },
    { role: "Brand Manager", access: "Create & update guidelines, approved terminology, and governance rules." },
    { role: "Fact Owner", access: "Authoritative registration and lifecycle maintenance of verified facts & SLAs." },
    { role: "Reviewer", access: "Inspect drafts, verify citations, and issue human approvals or change requests." },
    { role: "Creator", access: "Upload draft content, inspect automated findings, and submit revisions." },
  ];

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl mx-auto">
        <div>
          <h1 className="page-title text-3xl text-ink">Settings</h1>
          <p className="text-xs text-ink-soft mt-1">
            Organization profile and team permissions.
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
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Organization Profile</CardTitle>
                </div>
                <Badge variant="status" value="Active" />
              </CardHeader>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
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
              </div>
            </Card>

            {/* Role-Based Access Control (RBAC) Overview */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Role-Based Access Control (RBAC) Matrix</CardTitle>
                </div>
              </CardHeader>

              <div className="divide-y divide-line text-xs">
                {rolesMatrix.map((item) => (
                  <div key={item.role} className="py-2.5 flex items-start justify-between gap-4">
                    <div className="space-y-0.5">
                      <span className="font-semibold text-ink">{item.role}</span>
                      <p className="text-ink-soft">{item.access}</p>
                    </div>
                    {user?.role === item.role && (
                      <span className="px-2 py-0.5 rounded bg-accent-soft text-accent-ink border border-accent/20 font-semibold text-[11px] shrink-0">
                        Your Role
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </Card>

            {/* Team Members List */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-accent-ink" />
                  <CardTitle>Organization Members ({members.length})</CardTitle>
                </div>
              </CardHeader>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-ink-soft font-medium">
                      <th className="pb-2">Name</th>
                      <th className="pb-2">Email</th>
                      <th className="pb-2">Title</th>
                      <th className="pb-2">Role</th>
                      <th className="pb-2 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {members.map((m) => (
                      <tr key={m.id} className="hover:bg-sunken/60">
                        <td className="py-2.5 font-medium text-ink">{m.full_name}</td>
                        <td className="py-2.5 text-ink-soft font-mono text-[11px]">{m.email}</td>
                        <td className="py-2.5 text-ink">{m.title || "—"}</td>
                        <td className="py-2.5">
                          <span className="px-2 py-0.5 rounded bg-sunken text-accent-ink font-medium text-[11px] border border-line-strong">
                            {m.role}
                          </span>
                        </td>
                        <td className="py-2.5 text-right">
                          <Badge variant="status" value={m.is_active ? "Active" : "Disabled"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
