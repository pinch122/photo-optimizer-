"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchMedia, getTrashCount } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import Link from "next/link";
import {
  Library,
  Sparkles,
  PieChart,
  Activity,
  Copy,
  ShieldAlert,
  Monitor,
  FileText,
  ArrowRight,
  FolderOpen,
  Star,
  Clock,
  Search,
  Trash2,
  Calendar,
  HardDrive
} from "lucide-react";

// Hamming distance calculator for pHash matching
function getHammingDistance(hex1: string, hex2: string): number {
  if (!hex1 || !hex2 || hex1.length !== hex2.length) return 999;
  let distance = 0;
  for (let i = 0; i < hex1.length; i++) {
    const val1 = parseInt(hex1[i], 16);
    const val2 = parseInt(hex2[i], 16);
    let diff = val1 ^ val2;
    while (diff > 0) {
      if (diff & 1) distance++;
      diff >>= 1;
    }
  }
  return distance;
}

function isLowQualityPhoto(item: any): boolean {
  const quality = item.quality_assessment;
  if (!quality) return false;

  const grade = quality.quality_grade?.toUpperCase();
  if (grade === "GOOD" || grade === "EXCELLENT") return false;
  if (grade === "POOR" || grade === "VERY_POOR") return true;

  if (Array.isArray(quality.issues) && quality.issues.length > 0) {
    return quality.issues.some((issue: string) =>
      ["MOTION_BLUR", "OUT_OF_FOCUS", "LOW_RESOLUTION"].includes(issue)
    );
  }
  return false;
}

export default function AnalyticsPage() {
  const [customCollectionsCount, setCustomCollectionsCount] = useState(0);
  const [recentSearchesCount, setRecentSearchesCount] = useState(0);

  useEffect(() => {
    try {
      const storedCustom = localStorage.getItem("photomind_custom_collections");
      if (storedCustom) {
        const parsed = JSON.parse(storedCustom);
        setCustomCollectionsCount(Array.isArray(parsed) ? parsed.length : 0);
      }
    } catch {
      setCustomCollectionsCount(0);
    }

    try {
      const storedSearches = localStorage.getItem("photomind_recent_searches");
      if (storedSearches) {
        const parsed = JSON.parse(storedSearches);
        setRecentSearchesCount(Array.isArray(parsed) ? parsed.length : 0);
      }
    } catch {
      setRecentSearchesCount(0);
    }
  }, []);

  const { data: mediaData, isLoading: isLoadingMedia } = useQuery({
    queryKey: ["analytics-data"],
    queryFn: () => searchMedia("photo", 50000, 0),
  });

  const { data: trashData } = useQuery({
    queryKey: ["analytics-trash-count"],
    queryFn: () => getTrashCount(),
  });

  const items = mediaData?.items || [];
  const totalPhotos = mediaData?.total || items.length;
  const totalSize = items.reduce((sum, item) => sum + item.file_size, 0);

  // 1. Library Overview metrics
  const totalCollections = 8 + customCollectionsCount;
  const favoritesCount = items.filter(
    (item) => item.ai_analysis?.keywords?.favorite === true
  ).length;

  const now = Date.now();
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  const recentlyAddedCount = items.filter((item) => {
    const date = new Date(item.created_at || item.taken_at).getTime();
    return !isNaN(date) && now - date <= thirtyDaysMs;
  }).length;

  const photosAddedThisWeek = items.filter((item) => {
    const date = new Date(item.created_at || item.taken_at).getTime();
    return !isNaN(date) && now - date <= sevenDaysMs;
  }).length;

  const deletedPhotosCount = trashData?.count || 0;

  // 2. AI Insights calculations
  // Duplicate detection logic (Exact + Near duplicates)
  let duplicateCount = 0;
  let duplicateSavings = 0;
  const visitedDupes = new Set<string>();

  for (let i = 0; i < items.length; i++) {
    const itemA = items[i];
    if (visitedDupes.has(itemA.id)) continue;

    const group = [itemA];
    for (let j = i + 1; j < items.length; j++) {
      const itemB = items[j];
      if (visitedDupes.has(itemB.id)) continue;

      let isMatch = false;
      if (itemA.p_hash && itemB.p_hash) {
        const dist = getHammingDistance(itemA.p_hash, itemB.p_hash);
        if (dist <= 4) isMatch = true;
      } else if (
        itemA.file_size === itemB.file_size &&
        itemA.filename.toLowerCase() === itemB.filename.toLowerCase()
      ) {
        isMatch = true;
      }

      if (isMatch) {
        group.push(itemB);
        visitedDupes.add(itemB.id);
      }
    }

    if (group.length > 1) {
      visitedDupes.add(itemA.id);
      duplicateCount += group.length - 1;
      const sorted = [...group].sort((a, b) => b.file_size - a.file_size);
      sorted.slice(1).forEach((dup) => {
        duplicateSavings += dup.file_size;
      });
    }
  }

  // Blurry / Low-Quality Photos
  const blurryPhotos = items.filter(isLowQualityPhoto);
  const blurryCount = blurryPhotos.length;
  const blurrySavings = blurryPhotos.reduce((sum, item) => sum + item.file_size, 0);

  // Screenshots
  const screenshots = items.filter((item) => {
    const fn = item.filename.toLowerCase();
    const caption = item.ai_analysis?.caption?.toLowerCase() || "";
    const docType = item.ai_analysis?.document_type?.toLowerCase() || "";
    return fn.includes("screenshot") || caption.includes("screenshot") || docType === "screenshot";
  });
  const screenshotCount = screenshots.length;

  // Documents
  const documents = items.filter((item) => {
    const docType = item.ai_analysis?.document_type?.toLowerCase();
    const text = item.ai_analysis?.detected_text;
    return (
      (docType && docType !== "screenshot") ||
      (text && text.length > 50) ||
      item.media_type === "DOCUMENT"
    );
  });
  const documentCount = documents.length;

  const totalPotentialSavings = duplicateSavings + blurrySavings;

  // 3. User-friendly Media Breakdown
  const formatCounts: Record<string, number> = {};
  items.forEach((item) => {
    const ext = item.filename.split(".").pop()?.toUpperCase() || "JPEG";
    let friendlyName = ext;
    if (ext === "JPG") friendlyName = "JPEG";
    else if (["PNG", "WEBP", "HEIC", "GIF", "BMP"].includes(ext)) friendlyName = ext;
    else if (item.media_type === "VIDEO" || ["MP4", "MOV", "AVI", "MKV"].includes(ext)) friendlyName = "Videos";
    else friendlyName = "Other";

    formatCounts[friendlyName] = (formatCounts[friendlyName] || 0) + 1;
  });

  const TOTAL_CAPACITY = 50 * 1024 * 1024 * 1024; // 50 GB
  const usedPercentage = Math.min(
    100,
    Math.max(totalSize > 0 ? 0.5 : 0, (totalSize / TOTAL_CAPACITY) * 100)
  );
  const remainingSize = Math.max(0, TOTAL_CAPACITY - totalSize);

  return (
    <>
      <PageHeader
        title="Library Analytics"
        description="Personalized report and insights into your photo library"
      />

      {isLoadingMedia ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-default p-6 h-64 animate-pulse bg-[var(--bg-secondary)]" />
            <div className="rounded-xl border border-default p-6 h-64 animate-pulse bg-[var(--bg-secondary)]" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 rounded-xl border border-default p-6 h-64 animate-pulse bg-[var(--bg-secondary)]" />
            <div className="rounded-xl border border-default p-6 h-64 animate-pulse bg-[var(--bg-secondary)]" />
          </div>
        </div>
      ) : (
        <>
          {/* Top Row: Card 1 (Library Overview) & Card 2 (AI Insights) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {/* Card 1 — Library Overview */}
            <div
              className="rounded-xl border border-default p-6 flex flex-col justify-between"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Library className="w-5 h-5 text-brand" />
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Library Overview
                  </h2>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                  <div
                    className="p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <span className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-tertiary)" }}>
                      Total Photos
                    </span>
                    <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                      {totalPhotos.toLocaleString()}
                    </span>
                  </div>

                  <div
                    className="p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <span className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-tertiary)" }}>
                      Collections
                    </span>
                    <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                      {totalCollections}
                    </span>
                  </div>

                  <div
                    className="p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <span className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-tertiary)" }}>
                      Favorites
                    </span>
                    <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                      {favoritesCount}
                    </span>
                  </div>

                  <div
                    className="p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <span className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-tertiary)" }}>
                      Recently Added
                    </span>
                    <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                      {recentlyAddedCount}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-[var(--border-default)] space-y-2">
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>Storage Used</span>
                  <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                    {formatFileSize(totalSize)} of 50 GB
                  </span>
                </div>
                <div className="h-2 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                  <div
                    className="h-full bg-brand rounded-full transition-all duration-500"
                    style={{ width: `${usedPercentage}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                  <span>Remaining Space</span>
                  <span className="font-medium" style={{ color: "var(--text-secondary)" }}>
                    {formatFileSize(remainingSize)} available
                  </span>
                </div>
              </div>
            </div>

            {/* Card 2 — AI Insights */}
            <div
              className="rounded-xl border border-default p-6 flex flex-col justify-between"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    AI Insights
                  </h2>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <div className="p-2 rounded-md bg-blue-500/10 text-blue-400 flex-shrink-0">
                      <Copy className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[11px] font-medium block truncate" style={{ color: "var(--text-tertiary)" }}>
                        Duplicates Found
                      </span>
                      <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                        {duplicateCount}
                      </span>
                    </div>
                  </div>

                  <div
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <div className="p-2 rounded-md bg-amber-500/10 text-amber-400 flex-shrink-0">
                      <ShieldAlert className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[11px] font-medium block truncate" style={{ color: "var(--text-tertiary)" }}>
                        Blurry Photos
                      </span>
                      <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                        {blurryCount}
                      </span>
                    </div>
                  </div>

                  <div
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400 flex-shrink-0">
                      <Monitor className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[11px] font-medium block truncate" style={{ color: "var(--text-tertiary)" }}>
                        Screenshots
                      </span>
                      <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                        {screenshotCount}
                      </span>
                    </div>
                  </div>

                  <div
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-default)]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    <div className="p-2 rounded-md bg-purple-500/10 text-purple-400 flex-shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[11px] font-medium block truncate" style={{ color: "var(--text-tertiary)" }}>
                        Documents
                      </span>
                      <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                        {documentCount}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-[var(--border-default)] flex items-center justify-between">
                <div>
                  <span className="text-[11px] block" style={{ color: "var(--text-tertiary)" }}>
                    Potential space savings
                  </span>
                  <span className="text-xs font-semibold text-emerald-400">
                    {totalPotentialSavings > 0 ? formatFileSize(totalPotentialSavings) : "0 B"}
                  </span>
                </div>

                <Link
                  href="/recommendations"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-brand hover:bg-brand/10 transition-colors"
                >
                  Review Suggestions
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Bottom Row: Card 3 (Media Breakdown) & Card 4 (Recent Activity) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 3 — Media Breakdown */}
            <div
              className="md:col-span-2 rounded-xl border border-default p-6 flex flex-col justify-between"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <PieChart className="w-5 h-5 text-brand" />
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Media Breakdown
                  </h2>
                </div>

                <div className="space-y-3">
                  {Object.keys(formatCounts).length === 0 ? (
                    <p className="text-sm py-4" style={{ color: "var(--text-tertiary)" }}>
                      No media analyzed yet
                    </p>
                  ) : (
                    Object.entries(formatCounts)
                      .sort((a, b) => b[1] - a[1])
                      .map(([formatName, count]) => {
                        const pct = totalPhotos > 0 ? Math.round((count / totalPhotos) * 100) : 0;
                        return (
                          <div key={formatName}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="font-medium" style={{ color: "var(--text-secondary)" }}>
                                {formatName}
                              </span>
                              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                                {count.toLocaleString()} ({pct}%)
                              </span>
                            </div>
                            <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                              <div className="h-full bg-brand rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })
                  )}
                </div>
              </div>
            </div>

            {/* Card 4 — Recent Activity */}
            <div
              className="rounded-xl border border-default p-6 flex flex-col justify-between"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Activity className="w-5 h-5 text-blue-400" />
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Recent Activity
                  </h2>
                </div>

                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-brand/10 text-brand flex-shrink-0 mt-0.5">
                      <Calendar className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        Photos Added This Week
                      </span>
                      <p className="text-sm font-semibold mt-0.5" style={{ color: "var(--text-primary)" }}>
                        {photosAddedThisWeek}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 flex-shrink-0 mt-0.5">
                      <Search className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        Searches Performed
                      </span>
                      <p className="text-sm font-semibold mt-0.5" style={{ color: "var(--text-primary)" }}>
                        {recentSearchesCount > 0 ? recentSearchesCount : "No searches yet"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 flex-shrink-0 mt-0.5">
                      <FolderOpen className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        Collections Created
                      </span>
                      <p className="text-sm font-semibold mt-0.5" style={{ color: "var(--text-primary)" }}>
                        {totalCollections}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-red-500/10 text-red-400 flex-shrink-0 mt-0.5">
                      <Trash2 className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        Photos Deleted
                      </span>
                      <p className="text-sm font-semibold mt-0.5" style={{ color: "var(--text-primary)" }}>
                        {deletedPhotosCount}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
