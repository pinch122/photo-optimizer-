"use client";

import Link from "next/link";
import { Search, Upload, BarChart3 } from "lucide-react";

const actions = [
  {
    href: "/search",
    label: "Search Memories",
    description: "Find photos using natural language",
    icon: Search,
    iconColor: "var(--accent-primary)",
  },
  {
    href: "/upload",
    label: "Upload Photos",
    description: "Add new photos to your library",
    icon: Upload,
    iconColor: "var(--success)",
  },
  {
    href: "/analytics",
    label: "View Analytics",
    description: "Storage and processing metrics",
    icon: BarChart3,
    iconColor: "var(--warning)",
  },
];

export default function QuickActions() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {actions.map((action) => (
        <Link
          key={action.href}
          href={action.href}
          className="group rounded-lg border border-default p-5 transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-sm"
          style={{ backgroundColor: "var(--bg-secondary)" }}
        >
          <div
            className="flex items-center justify-center w-10 h-10 rounded-lg mb-3 transition-transform duration-200 group-hover:scale-110"
            style={{ backgroundColor: `${action.iconColor}15` }}
          >
            <action.icon className="w-5 h-5" style={{ color: action.iconColor }} />
          </div>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {action.label}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            {action.description}
          </p>
        </Link>
      ))}
    </div>
  );
}
