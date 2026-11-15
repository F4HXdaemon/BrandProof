import React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center px-6 py-12 rounded-lg border border-dashed border-line-strong",
        className
      )}
    >
      {icon && <div className="text-ink-mute mb-3">{icon}</div>}
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      {description && (
        <p className="text-xs text-ink-soft max-w-sm mt-1">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
