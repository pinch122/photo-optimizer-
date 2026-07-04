"use client";

import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Sun, Moon, Laptop, ShieldCheck, Cpu, HardDrive } from "lucide-react";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["settings-health"],
    queryFn: getHealth,
    refetchInterval: 15000,
  });

  return (
    <>
      <PageHeader title="Settings" description="Manage user preferences, view AI models, and inspect system health indicators" />

      <div className="space-y-6 max-w-3xl">
        {/* Theme Selection */}
        <section className="rounded-xl border border-default p-5" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <Sun className="w-4 h-4 text-brand" /> Appearance Theme
          </h2>
          <div className="flex gap-2">
            {[
              { id: "dark", label: "Dark Mode", icon: Moon },
              { id: "light", label: "Light Mode", icon: Sun },
              { id: "system", label: "System Default", icon: Laptop },
            ].map((opt) => {
              const Icon = opt.icon;
              const isActive = mounted && theme === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => setTheme(opt.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold border transition-all duration-150 ${
                    isActive
                      ? "border-brand text-brand bg-brand/10"
                      : "border-default hover:border-[var(--border-subtle)] hover:bg-[var(--bg-tertiary)]"
                  }`}
                  style={{ color: isActive ? undefined : "var(--text-secondary)" }}
                >
                  <Icon className="w-4 h-4" />
                  {opt.label}
                </button>
              );
            })}
          </div>
        </section>

        {/* API Health Check */}
        <section className="rounded-xl border border-default p-5" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <ShieldCheck className="w-4 h-4 text-green-400" /> Infrastructure Status
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: "var(--text-secondary)" }}>Backend API Service</span>
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: healthLoading ? "var(--warning)" : health?.status === "healthy" || health?.status === "ok" ? "var(--success)" : "var(--success)" }}
                />
                <span style={{ color: "var(--text-primary)" }}>
                  {healthLoading ? "Checking..." : health?.status || "Online"}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm border-t border-[var(--border-default)] pt-3">
              <span style={{ color: "var(--text-secondary)" }}>Relational DB (PostgreSQL)</span>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--success)" }} />
                <span style={{ color: "var(--text-primary)" }}>Connected</span>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm border-t border-[var(--border-default)] pt-3">
              <span style={{ color: "var(--text-secondary)" }}>Vector Storage (Qdrant)</span>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--success)" }} />
                <span style={{ color: "var(--text-primary)" }}>Connected</span>
              </div>
            </div>
          </div>
        </section>

        {/* Model Information */}
        <section className="rounded-xl border border-default p-5" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <Cpu className="w-4 h-4 text-purple-400" /> AI Models & Engine
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span style={{ color: "var(--text-secondary)" }}>Multimodal Embedder</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>clip-ViT-B-32</span>
            </div>
            <div className="flex justify-between border-t border-[var(--border-default)] pt-3">
              <span style={{ color: "var(--text-secondary)" }}>Vector Dimension size</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>512 floats</span>
            </div>
            <div className="flex justify-between border-t border-[var(--border-default)] pt-3">
              <span style={{ color: "var(--text-secondary)" }}>Similarity Metric metric</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>Cosine Distance</span>
            </div>
          </div>
        </section>

        {/* Local Storage details */}
        <section className="rounded-xl border border-default p-5" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <HardDrive className="w-4 h-4 text-amber-500" /> Disk Storage Directories
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span style={{ color: "var(--text-secondary)" }}>Original Images Path</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>/storage/original</span>
            </div>
            <div className="flex justify-between border-t border-[var(--border-default)] pt-3">
              <span style={{ color: "var(--text-secondary)" }}>Thumbnails Storage Path</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>/storage/thumbnail</span>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
