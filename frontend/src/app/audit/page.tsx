"use client";

import React, { useEffect, useState, useCallback } from "react";
import { History, Filter, RefreshCw, UserCheck, Shield } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api";
import { AuditEvent } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function AuditLogPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [entityFilter, setEntityFilter] = useState("All");

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.audit.list({
        action: actionFilter || undefined,
        entity_type: entityFilter === "All" ? undefined : entityFilter,
        limit: 50,
      });
      setEvents(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [actionFilter, entityFilter]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const entities = ["All", "Document", "Review", "Approval", "Fact", "Guideline", "Term", "Rule", "User"];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="page-title text-3xl text-ink">Audit log</h1>
            <p className="text-xs text-ink-soft mt-1">
              Every upload, evaluation, policy change and approval, in order.
            </p>
          </div>

          <Button variant="outline" size="sm" onClick={fetchEvents} isLoading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Audit Log</span>
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-lg bg-surface border border-line">
          <input
            type="text"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="Filter by action (e.g. APPROVAL, UPLOAD, FACT)..."
            className="w-full sm:w-72 bg-paper border border-line-strong rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent"
          />

          <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto">
            <span className="text-xs text-ink-mute mr-1 shrink-0">Entity:</span>
            {entities.map((ent) => (
              <button
                key={ent}
                onClick={() => setEntityFilter(ent)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                  entityFilter === ent
                    ? "bg-accent text-ink font-semibold"
                    : "text-ink-soft hover:text-ink hover:bg-sunken"
                }`}
              >
                {ent}
              </button>
            ))}
          </div>
        </div>

        {/* Audit Events Table */}
        <Card className="p-0 overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : events.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-paper border-b border-line text-ink-soft font-medium">
                  <tr>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Actor</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Entity Type</th>
                    <th className="py-3 px-4">Entity ID</th>
                    <th className="py-3 px-4">Metadata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line font-mono text-[11px]">
                  {events.map((e) => (
                    <tr key={e.id} className="hover:bg-sunken/60 transition-colors">
                      <td className="py-2.5 px-4 text-ink-soft whitespace-nowrap">
                        {formatDate(e.timestamp)}
                      </td>
                      <td className="py-2.5 px-4 font-sans text-ink font-medium whitespace-nowrap">
                        {e.actor_name || "System"}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded bg-sunken text-accent-ink border border-line-strong font-semibold">
                          {e.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-ink font-sans">{e.entity_type}</td>
                      <td className="py-2.5 px-4 text-ink-mute truncate max-w-[120px]">{e.entity_id}</td>
                      <td className="py-2.5 px-4 text-ink-soft truncate max-w-xs font-mono text-[11px]">
                        {JSON.stringify(e.metadata || {})}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8">
              <EmptyState
                icon={<History className="w-6 h-6 text-accent-ink" />}
                title="No audit events found"
                description="Events will appear here as users upload content, approve reviews, or update knowledge facts."
              />
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
