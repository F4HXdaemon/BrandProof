import React from "react";
import { cn, getStatusBadgeClass, getSeverityBadgeClass } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "status" | "severity" | "default" | "outline";
  value?: string;
}

export function Badge({
  children,
  className,
  variant = "default",
  value,
  ...props
}: BadgeProps) {
  let variantClass = "bg-sunken text-ink-soft border-line";

  if (variant === "status" && value) {
    variantClass = getStatusBadgeClass(value);
  } else if (variant === "severity" && value) {
    variantClass = getSeverityBadgeClass(value);
  } else if (variant === "outline") {
    variantClass = "border-line-strong text-ink-soft bg-transparent";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border whitespace-nowrap",
        variantClass,
        className
      )}
      {...props}
    >
      {children || value}
    </span>
  );
}
