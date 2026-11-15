import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString?: string): string {
  if (!dateString) return "N/A";
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "N/A";
  try {
    const d = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 30) return `${diffDays}d ago`;
    return formatDate(dateString);
  } catch {
    return dateString;
  }
}

export function getStatusBadgeClass(status: string): string {
  switch (status) {
    case "Approved":
    case "Active":
    case "Verified":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    case "Expiring":
    case "Expiring Soon":
    case "Needs Review":
    case "In Progress":
    case "Proposed":
      return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    case "Changes Requested":
    case "Disputed":
      return "bg-orange-500/10 text-orange-400 border-orange-500/20";
    case "Rejected":
    case "Critical":
    case "Blocker":
    case "Expired":
      return "bg-rose-500/10 text-rose-400 border-rose-500/20";
    case "Draft":
      return "bg-accent-soft text-accent-ink border-accent/20";
    case "Archived":
    case "Deprecated":
      return "bg-sunken text-ink-soft border-line-strong";
    default:
      return "bg-sunken text-ink-soft border-line-strong";
  }
}

export function getSeverityBadgeClass(severity: string): string {
  switch (severity) {
    case "Blocker":
    case "Critical":
      return "bg-rose-500/15 text-rose-400 border-rose-500/30";
    case "High":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "Warning":
    case "Medium":
      return "bg-yellow-500/15 text-yellow-400 border-yellow-500/30";
    case "Info":
    case "Low":
    case "Advisory":
      return "bg-sky-500/15 text-sky-400 border-sky-500/30";
    default:
      return "bg-sunken text-ink-soft border-line-strong";
  }
}

export function getFactExpiryBadge(fact: {
  status: string;
  effective_status?: string;
  is_expired?: boolean;
  days_until_expiry?: number | null;
  expires_at?: string;
}): { label: string; colorClass: string; icon: "check" | "clock" | "alert" | "archive" } {
  const effStatus = fact.effective_status || fact.status;

  if (effStatus === "Archived" || fact.status === "Archived") {
    return {
      label: "Archived",
      colorClass: "bg-sunken text-ink-soft border-line-strong",
      icon: "archive",
    };
  }

  if (fact.is_expired || effStatus === "Expired") {
    const daysAgo =
      fact.days_until_expiry !== null && fact.days_until_expiry !== undefined
        ? Math.abs(fact.days_until_expiry)
        : null;
    return {
      label: daysAgo !== null ? `Expired ${daysAgo}d ago` : "Expired",
      colorClass: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      icon: "alert",
    };
  }

  if (
    fact.days_until_expiry !== null &&
    fact.days_until_expiry !== undefined &&
    fact.days_until_expiry <= 30
  ) {
    return {
      label: `Expires in ${fact.days_until_expiry}d`,
      colorClass: "bg-amber-500/20 text-amber-300 border-amber-500/40",
      icon: "clock",
    };
  }

  if (fact.expires_at && fact.days_until_expiry !== null && fact.days_until_expiry !== undefined) {
    return {
      label: `Expires in ${fact.days_until_expiry}d`,
      colorClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
      icon: "check",
    };
  }

  return {
    label: "Permanent Truth",
    colorClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    icon: "check",
  };
}
