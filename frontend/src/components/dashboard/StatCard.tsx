"use client";

import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconColor?: string;
  loading?: boolean;
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconColor = "var(--accent-primary)",
  loading = false,
}: StatCardProps) {
  if (loading) {
    return (
      <div
        className="rounded-lg border border-default p-6"
        style={{ backgroundColor: "var(--bg-secondary)" }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg skeleton" />
          <div className="w-24 h-4 rounded skeleton" />
        </div>
        <div className="w-20 h-8 rounded skeleton mb-2" />
        <div className="w-16 h-3 rounded skeleton" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-default p-6 transition-all duration-200",
        "hover:border-[var(--border-subtle)] hover:shadow-sm"
      )}
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      <div className="flex items-center gap-3 mb-4">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-lg"
          style={{ backgroundColor: `${iconColor}15` }}
        >
          <Icon className="w-5 h-5" style={{ color: iconColor }} />
        </div>
        <span className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          {title}
        </span>
      </div>
      <div className="text-3xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
        {value}
      </div>
      {subtitle && (
        <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
