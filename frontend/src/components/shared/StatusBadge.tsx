"use client";

import { cn } from "@/lib/utils";
import type { AssetStatus } from "@/lib/types";

const statusConfig: Record<AssetStatus, { color: string; label: string }> = {
  UPLOADED: { color: "var(--info)", label: "Uploaded" },
  PROCESSING: { color: "var(--warning)", label: "Processing" },
  READY: { color: "var(--success)", label: "Ready" },
  FAILED: { color: "var(--error)", label: "Failed" },
};

interface StatusBadgeProps {
  status: AssetStatus;
  className?: string;
}

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", className)}>
      <span
        className={cn("w-1.5 h-1.5 rounded-full", status === "PROCESSING" && "animate-pulse-dot")}
        style={{ backgroundColor: config.color }}
      />
      <span style={{ color: config.color }}>{config.label}</span>
    </span>
  );
}
