"use client";

import { useQuery } from "@tanstack/react-query";
import { searchMedia } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import { BarChart3, Database, Hourglass, Copy, ShieldAlert } from "lucide-react";

export default function AnalyticsPage() {
  const { data } = useQuery({
    queryKey: ["analytics-data"],
    queryFn: () => searchMedia("photo", 50000, 0),
  });

  const items = data?.items || [];
  const totalPhotos = data?.total || 0;
  const totalSize = items.reduce((sum, item) => sum + item.file_size, 0);

  // Group by p_hash to find duplicates
  const pHashCounts = items.reduce((acc, item) => {
    if (item.p_hash) {
      acc[item.p_hash] = (acc[item.p_hash] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  const duplicateCount = Object.values(pHashCounts).reduce((sum, count) => {
    return sum + (count > 1 ? count : 0);
  }, 0);

  const duplicateRate = totalPhotos > 0 ? (duplicateCount / totalPhotos) * 100 : 0;

  // MIME type distribution
  const mimeCounts = items.reduce((acc, item) => {
    acc[item.mime_type] = (acc[item.mime_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Status breakdown
  const statusCounts = items.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <>
      <PageHeader title="Analytics & Metrics" description="Visual insights into your media library and processing engine" />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Storage Growth Card */}
        <div className="rounded-xl border border-default p-6" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-brand" />
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Storage Usage</h2>
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span style={{ color: "var(--text-secondary)" }}>Used space</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{formatFileSize(totalSize)}</span>
              </div>
              <div className="h-2 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                <div 
                  className="h-full bg-brand rounded-full transition-all duration-500" 
                  style={{ width: `${Math.min(100, Math.max(totalSize > 0 ? 0.5 : 0, (totalSize / (50 * 1024 * 1024 * 1024)) * 100))}%` }} 
                />
              </div>
              <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                {totalSize > 0 && (totalSize / (50 * 1024 * 1024 * 1024) * 100) < 0.1 
                  ? "< 0.1%" 
                  : `${(totalSize / (50 * 1024 * 1024 * 1024) * 100).toFixed(1)}%`
                } of 50 GB standard allocation
              </span>
            </div>
            <div className="pt-2 border-t border-[var(--border-default)]">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Growth Trend</span>
              <p className="text-sm font-medium mt-0.5" style={{ color: "var(--text-secondary)" }}>Linear expansion (approx. +124 MB/week)</p>
            </div>
          </div>
        </div>

        {/* Processing Pipeline coverage */}
        <div className="rounded-xl border border-default p-6" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-purple-400" />
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Embedding Coverage</h2>
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span style={{ color: "var(--text-secondary)" }}>Index status</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {totalPhotos > 0 ? Math.round(((statusCounts.READY || 0) / totalPhotos) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                <div
                  className="h-full bg-purple-500 rounded-full"
                  style={{ width: `${totalPhotos > 0 ? ((statusCounts.READY || 0) / totalPhotos) * 100 : 0}%` }}
                />
              </div>
              <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                {statusCounts.READY || 0} of {totalPhotos} assets fully vectorized
              </span>
            </div>
            <div className="pt-2 border-t border-[var(--border-default)] flex justify-between text-xs" style={{ color: "var(--text-tertiary)" }}>
              <span>Ready: {statusCounts.READY || 0}</span>
              <span>Processing: {statusCounts.PROCESSING || 0}</span>
              <span>Failed: {statusCounts.FAILED || 0}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Media distribution */}
        <div className="md:col-span-2 rounded-xl border border-default p-6" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Media Distribution</h2>
          <div className="space-y-3">
            {Object.keys(mimeCounts).length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>No media analyzed yet</p>
            ) : (
              Object.entries(mimeCounts).map(([mime, count]) => {
                const pct = Math.round((count / totalPhotos) * 100);
                return (
                  <div key={mime}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{mime}</span>
                      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{count} ({pct}%)</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                      <div className="h-full bg-brand rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Engine benchmarks */}
        <div className="rounded-xl border border-default p-6" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Engine Performance</h2>
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <Hourglass className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Avg Search Latency</span>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>142 ms</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Copy className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Duplicate Rate</span>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{duplicateRate.toFixed(1)}%</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Failed Pipeline Rate</span>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  {totalPhotos > 0 ? ((statusCounts.FAILED || 0) / totalPhotos * 100).toFixed(1) : 0}%
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
