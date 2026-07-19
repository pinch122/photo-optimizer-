"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Image,
  Upload,
  Search,
  BarChart3,
  FolderOpen,
  Settings,
  Brain,
  PanelLeftClose,
  PanelLeft,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/gallery", label: "Gallery", icon: Image },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/search", label: "Search", icon: Search },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/recommendations", label: "Recommendations", icon: Sparkles },
  { href: "/collections", label: "Collections", icon: FolderOpen },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "hidden lg:flex flex-col h-screen sticky top-0 border-r border-default transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-default">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand/20">
          <Brain className="w-5 h-5 text-brand" />
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
            PhotoMind AI
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150",
                isActive
                  ? "bg-brand/10 text-brand border-l-2 border-brand"
                  : "hover:bg-[var(--bg-tertiary)]",
                collapsed && "justify-center px-0"
              )}
              style={{
                color: isActive ? undefined : "var(--text-secondary)",
              }}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-default">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            "flex items-center gap-3 w-full px-3 py-2 rounded-md text-sm transition-colors duration-150 hover:bg-[var(--bg-tertiary)]",
            collapsed && "justify-center px-0"
          )}
          style={{ color: "var(--text-tertiary)" }}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="w-5 h-5" />
          ) : (
            <>
              <PanelLeftClose className="w-5 h-5" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
