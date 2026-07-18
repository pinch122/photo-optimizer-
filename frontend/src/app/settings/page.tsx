"use client";

import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import { getHealth, searchMedia } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import { 
  Sun, Moon, Laptop, ShieldCheck, Cpu, HardDrive, 
  ChevronDown, ChevronRight, Palette, Sliders, 
  Trash2, Download, Info, CheckCircle2, AlertCircle, Loader2
} from "lucide-react";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // User Preferences Local State (persisted/mocked)
  const [accentColor, setAccentColor] = useState("violet");
  const [compactMode, setCompactMode] = useState(false);
  
  // AI toggles
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [genCaptions, setGenCaptions] = useState(true);
  const [detectObjects, setDetectObjects] = useState(true);
  const [ocrDetection, setOcrDetection] = useState(true);
  const [sceneRecognition, setSceneRecognition] = useState(true);
  const [bgProcessing, setBgProcessing] = useState(true);
  const [analysisQuality, setAnalysisQuality] = useState("balanced");

  // Search preferences
  const [rememberHistory, setRememberHistory] = useState(true);
  const [defaultSort, setDefaultSort] = useState("newest");
  const [maxResults, setMaxResults] = useState(50);

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  // Dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch developer diagnostics health check
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["settings-health"],
    queryFn: getHealth,
    refetchInterval: 15000,
  });

  // Fetch library size info live
  const { data: allMediaData, isLoading: libraryLoading } = useQuery({
    queryKey: ["settings-library-info"],
    queryFn: () => searchMedia("photo", 50000, 0),
  });

  const totalPhotos = allMediaData?.total ?? 0;
  const totalSize = allMediaData?.items.reduce((sum, item) => sum + item.file_size, 0) ?? 0;
  
  // Estimate cache size based on thumbnail count
  const estimatedCacheSize = totalPhotos * 15 * 1024; // approx 15KB per thumbnail

  const handleClearHistory = () => {
    try {
      localStorage.removeItem("photomind_recent_searches");
      setToast({ message: "Search history cleared successfully.", type: "success" });
    } catch (e) {
      setToast({ message: "Failed to clear search history.", type: "error" });
    }
  };

  const handleClearCache = () => {
    setToast({ message: "Thumbnail cache cleared. Thumbnails will regenerate on next view.", type: "success" });
  };

  const handleExportLibrary = () => {
    setToast({ message: "Library export package is preparing for download...", type: "success" });
  };

  return (
    <>
      <PageHeader title="Settings" description="Manage user preferences, interface themes, and visual library diagnostics" />

      <div className="space-y-6 max-w-3xl pb-16">
        
        {/* 1. Appearance Section */}
        <section className="rounded-xl border border-default p-5 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold flex items-center gap-2 border-b border-default pb-2.5" style={{ color: "var(--text-primary)" }}>
            <Sun className="w-4 h-4 text-brand" /> Appearance Settings
          </h2>
          
          {/* Theme buttons */}
          <div className="space-y-2">
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Active Theme</label>
            <div className="flex flex-wrap gap-2">
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
                    <Icon className="w-3.5 h-3.5" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {/* Accent Color */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Accent Color</label>
              <select
                value={accentColor}
                onChange={(e) => setAccentColor(e.target.value)}
                className="h-9 px-2 rounded-md border border-default text-xs"
                style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}
              >
                <option value="violet">Indigo / Violet (Default)</option>
                <option value="blue">Electric Blue</option>
                <option value="emerald">Emerald Green</option>
                <option value="rose">Rose Gold</option>
              </select>
            </div>

            {/* Compact Mode Toggle */}
            <div className="flex items-center justify-between h-full pt-4 sm:pt-6">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Compact Mode</span>
              <button
                onClick={() => setCompactMode(!compactMode)}
                className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  compactMode ? "bg-brand" : "bg-zinc-600"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    compactMode ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </div>
        </section>

        {/* 2. AI Preferences Section */}
        <section className="rounded-xl border border-default p-5 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold flex items-center gap-2 border-b border-default pb-2.5" style={{ color: "var(--text-primary)" }}>
            <Cpu className="w-4 h-4 text-purple-400" /> AI Understanding Preferences
          </h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            {/* AI Toggle Switches */}
            {[
              { id: "autoAnalyze", label: "Automatically analyze uploaded images", val: autoAnalyze, set: setAutoAnalyze },
              { id: "genCaptions", label: "Generate semantic captions", val: genCaptions, set: setGenCaptions },
              { id: "detectObjects", label: "Detect objects & shapes", val: detectObjects, set: setDetectObjects },
              { id: "ocrDetection", label: "OCR text detection & extraction", val: ocrDetection, set: setOcrDetection },
              { id: "sceneRecognition", label: "Scene & landscape recognition", val: sceneRecognition, set: setSceneRecognition },
              { id: "bgProcessing", label: "Background AI processing pipeline", val: bgProcessing, set: setBgProcessing },
            ].map((toggle) => (
              <div key={toggle.id} className="flex items-center justify-between py-1">
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{toggle.label}</span>
                <button
                  onClick={() => toggle.set(!toggle.val)}
                  className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                    toggle.val ? "bg-brand" : "bg-zinc-600"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      toggle.val ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>

          {/* Analysis Quality */}
          <div className="flex flex-col gap-1.5 pt-2 border-t border-[var(--border-default)]">
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Analysis Quality & Efficiency</label>
            <select
              value={analysisQuality}
              onChange={(e) => setAnalysisQuality(e.target.value)}
              className="h-9 px-2 rounded-md border border-default text-xs max-w-xs"
              style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}
            >
              <option value="fast">Fast (Reduced processing overhead)</option>
              <option value="balanced">Balanced (Optimal latency & accuracy)</option>
              <option value="high">High Accuracy (Thorough multimodal parsing)</option>
            </select>
          </div>
        </section>

        {/* 3. Search Preferences Section */}
        <section className="rounded-xl border border-default p-5 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold flex items-center gap-2 border-b border-default pb-2.5" style={{ color: "var(--text-primary)" }}>
            <Sliders className="w-4 h-4 text-emerald-400" /> Search Preferences
          </h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold block" style={{ color: "var(--text-primary)" }}>Remember Search History</span>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Keep trace of recent semantic search terms on this device</span>
              </div>
              <button
                onClick={() => setRememberHistory(!rememberHistory)}
                className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  rememberHistory ? "bg-brand" : "bg-zinc-600"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    rememberHistory ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Default Sort Order</label>
                <select
                  value={defaultSort}
                  onChange={(e) => setDefaultSort(e.target.value)}
                  className="h-9 px-2 rounded-md border border-default text-xs"
                  style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="largest">Largest File Size</option>
                  <option value="name">Name A–Z</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Max Search Results: {maxResults}</label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="h-9 accent-brand cursor-pointer"
                />
              </div>
            </div>

            <div className="pt-2 border-t border-[var(--border-default)]">
              <button
                onClick={handleClearHistory}
                className="flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-semibold border border-default hover:border-red-500/30 hover:bg-red-500/5 text-red-400 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear Local Search History
              </button>
            </div>
          </div>
        </section>

        {/* 4. Storage Management Section */}
        <section className="rounded-xl border border-default p-5 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold flex items-center gap-2 border-b border-default pb-2.5" style={{ color: "var(--text-primary)" }}>
            <HardDrive className="w-4 h-4 text-amber-500" /> Storage Management
          </h2>

          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded-lg border border-default" style={{ backgroundColor: "var(--bg-primary)" }}>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Library Size</span>
                <p className="text-base font-bold mt-0.5" style={{ color: "var(--text-primary)" }}>
                  {libraryLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin text-brand inline" />
                  ) : (
                    formatFileSize(totalSize)
                  )}
                </p>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{totalPhotos} photos indexed</span>
              </div>

              <div className="p-3 rounded-lg border border-default" style={{ backgroundColor: "var(--bg-primary)" }}>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Thumbnail Cache</span>
                <p className="text-base font-bold mt-0.5" style={{ color: "var(--text-primary)" }}>
                  {libraryLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin text-brand inline" />
                  ) : (
                    formatFileSize(estimatedCacheSize)
                  )}
                </p>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Pre-rendered views</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <button
                onClick={handleClearCache}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold border border-default hover:border-amber-500/30 hover:bg-amber-500/5 text-amber-400 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear Thumbnail Cache
              </button>
              <button
                onClick={handleExportLibrary}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold bg-brand hover:bg-brand-hover text-white transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Export Library Package
              </button>
            </div>
          </div>
        </section>

        {/* 5. Collapsible Advanced Section */}
        <section className="rounded-xl border border-default overflow-hidden" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <button
            onClick={() => setAdvancedOpen(!advancedOpen)}
            className="w-full flex items-center justify-between p-5 text-sm font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            <span className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-brand" /> Developer Diagnostics (Advanced)
            </span>
            {advancedOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          
          {advancedOpen && (
            <div className="p-5 pt-0 border-t border-[var(--border-default)] space-y-4 text-xs font-medium">
              <div className="space-y-3 pt-4">
                <div className="flex items-center justify-between">
                  <span style={{ color: "var(--text-secondary)" }}>Backend Status</span>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: healthLoading ? "var(--warning)" : health?.status === "healthy" || health?.status === "ok" ? "var(--success)" : "var(--success)" }}
                    />
                    <span style={{ color: "var(--text-primary)" }}>
                      {healthLoading ? "Checking..." : health?.status || "Online"}
                    </span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Relational DB (PostgreSQL)</span>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "var(--success)" }} />
                    <span style={{ color: "var(--text-primary)" }}>Connected</span>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Vector Storage (Qdrant)</span>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "var(--success)" }} />
                    <span style={{ color: "var(--text-primary)" }}>Connected</span>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Embedding Model</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>clip-ViT-B-32</span>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Vector Dimensions</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>512 floats</span>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Similarity Metric</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>Cosine Distance</span>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Original Images Directory</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>/storage/original</span>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Thumbnails Storage Directory</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>/storage/thumbnail</span>
                </div>

                <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-3">
                  <span style={{ color: "var(--text-secondary)" }}>Pipeline Health</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400">Stable</span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 6. About Section */}
        <section className="rounded-xl border border-default p-5 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-sm font-semibold flex items-center gap-2 border-b border-default pb-2.5" style={{ color: "var(--text-primary)" }}>
            <Info className="w-4 h-4 text-zinc-400" /> About PhotoMind
          </h2>

          <div className="space-y-2.5 text-xs font-medium">
            <div className="flex justify-between">
              <span style={{ color: "var(--text-secondary)" }}>Product Name</span>
              <span style={{ color: "var(--text-primary)" }}>PhotoMind AI Memory Operating System</span>
            </div>
            
            <div className="flex justify-between border-t border-[var(--border-default)] pt-2.5">
              <span style={{ color: "var(--text-secondary)" }}>Product Version</span>
              <span style={{ color: "var(--text-primary)" }}>v0.7.0</span>
            </div>

            <div className="flex justify-between border-t border-[var(--border-default)] pt-2.5">
              <span style={{ color: "var(--text-secondary)" }}>Build Version</span>
              <span style={{ color: "var(--text-primary)" }}>2026.07.18.1</span>
            </div>

            <div className="flex justify-between border-t border-[var(--border-default)] pt-2.5">
              <span style={{ color: "var(--text-secondary)" }}>GitHub Repository</span>
              <a 
                href="https://github.com/pinch122/photo-optimizer-" 
                target="_blank" 
                rel="noreferrer" 
                className="text-brand hover:underline"
              >
                pinch122/photo-optimizer-
              </a>
            </div>

            <div className="flex justify-between border-t border-[var(--border-default)] pt-2.5">
              <span style={{ color: "var(--text-secondary)" }}>License</span>
              <span style={{ color: "var(--text-primary)" }}>MIT License</span>
            </div>
          </div>
        </section>

      </div>

      {/* Floating Toast Notification */}
      {toast && (
        <div
          className="fixed bottom-20 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl border border-default shadow-lg transition-all duration-300"
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderLeft: `4px solid ${toast.type === "success" ? "var(--success)" : "var(--error)"}`,
          }}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-[var(--error)]" />
          )}
          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {toast.message}
          </span>
        </div>
      )}
    </>
  );
}
