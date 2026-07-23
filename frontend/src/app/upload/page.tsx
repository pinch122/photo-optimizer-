"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { uploadMedia, getMediaStatus } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import { Upload, CloudUpload, FileImage, X, RotateCw, Eye, CheckCircle2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AssetStatus } from "@/lib/types";

const MAX_CONCURRENT_UPLOADS = 5;

interface QueueItem {
  id: string;
  file: File;
  status: "queued" | "uploading" | "polling" | "done" | "error" | "duplicate";
  assetId?: string;
  assetStatus?: AssetStatus;
  error?: string;
  progress: number;
}

export default function UploadPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const updateItem = useCallback((id: string, updates: Partial<QueueItem>) => {
    setQueue((prev) => prev.map((item) => (item.id === id ? { ...item, ...updates } : item)));
  }, []);

  const pollStatus = useCallback(
    async (queueId: string, assetId: string) => {
      const poll = async () => {
        try {
          const status = await getMediaStatus(assetId);
          if (status.status === "READY") {
            updateItem(queueId, { status: "done", assetStatus: "READY", progress: 100 });
            setToast({ message: "Photo fully processed and ready!", type: "success" });
          } else if (status.status === "FAILED") {
            updateItem(queueId, { status: "error", assetStatus: "FAILED", error: status.error_message || "Processing failed" });
            setToast({ message: `Processing failed: ${status.error_message || "Unknown error"}`, type: "error" });
          } else {
            setTimeout(poll, 2000);
          }
        } catch {
          updateItem(queueId, { status: "error", error: "Failed to check status" });
        }
      };
      poll();
    },
    [updateItem]
  );

  // ── Core Bounded Upload Queue Scheduler ──────────────────────────────────
  const startUpload = useCallback(async (item: QueueItem) => {
    // Mark as uploading immediately to avoid double mutates
    updateItem(item.id, { status: "uploading", progress: 20 });
    
    try {
      const result = await uploadMedia(item.file);
      updateItem(item.id, {
        status: "polling",
        assetId: result.id,
        assetStatus: result.status,
        progress: 75,
        error: undefined
      });
      pollStatus(item.id, result.id);
    } catch (error: any) {
      const isConflict = error.response?.status === 409 || error.message?.includes("409");
      if (isConflict) {
        const duplicateId = error.response?.data?.detail?.duplicate_id;
        updateItem(item.id, {
          status: "duplicate",
          assetId: duplicateId,
          progress: 100,
          error: "This photo is already in your gallery."
        });
        setToast({ message: `Already in gallery: ${item.file.name}`, type: "success" });
      } else {
        const msg = error.response?.data?.detail?.message || error.response?.data?.detail || error.message || "Upload failed.";
        updateItem(item.id, { status: "error", error: msg, progress: 0 });
        setToast({ message: `Failed to upload ${item.file.name}: ${msg}`, type: "error" });
      }
    }
  }, [updateItem, pollStatus]);

  // Effect scheduler that triggers next uploads keeping concurrency <= MAX_CONCURRENT_UPLOADS
  useEffect(() => {
    const activeCount = queue.filter((item) => item.status === "uploading").length;
    if (activeCount >= MAX_CONCURRENT_UPLOADS) return;

    // Find all queued items
    const queuedItems = queue.filter((item) => item.status === "queued");
    if (queuedItems.length === 0) return;

    // Start as many as we can fit under the concurrency limit
    const slotsAvailable = MAX_CONCURRENT_UPLOADS - activeCount;
    const itemsToStart = queuedItems.slice(0, slotsAvailable);

    itemsToStart.forEach((item) => {
      startUpload(item);
    });
  }, [queue, startUpload]);

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const validTypes = ["image/jpeg", "image/png", "image/webp", "image/heic"];
      const newItems: QueueItem[] = Array.from(files)
        .filter((f) => validTypes.includes(f.type) || f.name.match(/\.(jpg|jpeg|png|webp|heic)$/i))
        .map((file) => ({
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          file,
          status: "queued" as const,
          progress: 0,
        }));

      setQueue((prev) => [...prev, ...newItems]);
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const removeItem = (id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  };

  const handleRetry = (id: string) => {
    updateItem(id, { status: "queued", progress: 0, error: undefined, assetStatus: undefined });
  };

  // ── Stats Calculations ───────────────────────────────────────────────────
  const totalCount = queue.length;
  const uploadingCount = queue.filter((i) => i.status === "uploading").length;
  const waitingCount = queue.filter((i) => i.status === "queued").length;
  const processingCount = queue.filter((i) => i.status === "polling").length;
  const readyCount = queue.filter((i) => i.status === "done").length;
  const failedCount = queue.filter((i) => i.status === "error").length;
  const duplicateCount = queue.filter((i) => i.status === "duplicate").length;

  const completedCount = readyCount + failedCount + duplicateCount;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <>
      <PageHeader title="Upload Photos" description="Add new photos to your PhotoMind AI library" />

      {/* Drag & Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative rounded-xl border-2 border-dashed p-12 text-center cursor-pointer
          transition-all duration-200
          ${isDragging
            ? "border-brand bg-brand/5 scale-[1.01]"
            : "border-[var(--border-subtle)] hover:border-brand/50 hover:bg-[var(--bg-secondary)]"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/heic"
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
        <CloudUpload
          className="w-12 h-12 mx-auto mb-4 transition-transform duration-200"
          style={{ color: isDragging ? "var(--accent-primary)" : "var(--text-tertiary)" }}
        />
        <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>
          Drag and drop your photos here
        </p>
        <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>
          or click to browse files
        </p>
        <p className="text-xs mt-3" style={{ color: "var(--text-tertiary)" }}>
          Supports: JPEG, PNG, WebP, HEIC · Maximum: 50MB per file
        </p>
      </div>

      {/* ── Bounded Upload Queue Progress Bar & Stats panel ───────────────── */}
      {totalCount > 0 && (
        <div
          className="mt-8 p-6 rounded-2xl border border-default space-y-6"
          style={{ backgroundColor: "var(--bg-secondary)" }}
        >
          {/* Header & Status */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                {completedCount === totalCount ? "All uploads completed" : `Uploading ${totalCount} photos`}
              </h2>
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                Overall progress: <span className="font-bold text-[var(--text-primary)]">{completedCount} / {totalCount} complete</span>
              </p>
            </div>
            <span className="text-sm font-black text-brand bg-brand/10 px-3 py-1 rounded-lg border border-brand/20">
              {progressPercent}%
            </span>
          </div>

          {/* Smooth Overall Progress Bar */}
          <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
            <div
              className="h-full rounded-full transition-all duration-500 bg-brand"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Current Activity Stats Breakdown */}
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 pt-2 border-t border-default">
            {/* 1. Uploading */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-amber-400">{uploadingCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">Uploading</p>
            </div>

            {/* 2. Waiting */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-zinc-400">{waitingCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">Waiting</p>
            </div>

            {/* 3. Processing */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-blue-400 animate-pulse">{processingCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">Processing</p>
            </div>

            {/* 4. Ready */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-emerald-400">{readyCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">Ready</p>
            </div>

            {/* 5. Failed */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-rose-400">{failedCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">Failed</p>
            </div>

            {/* 6. Already in Gallery */}
            <div className="p-3 rounded-xl bg-[var(--bg-tertiary)] text-center space-y-1">
              <span className="text-lg font-black text-zinc-500">{duplicateCount}</span>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">In Gallery</p>
            </div>
          </div>
        </div>
      )}

      {/* Queue Items List */}
      {queue.length > 0 && (
        <div className="mt-8 space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              Files ({queue.length})
            </h3>
            <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-secondary)" }}>
              {readyCount > 0 && <span className="text-[var(--success)]">✓ {readyCount} ready</span>}
              {processingCount > 0 && <span className="text-[var(--warning)]">⏳ {processingCount} processing</span>}
              {duplicateCount > 0 && <span className="text-zinc-500">📁 {duplicateCount} in gallery</span>}
              {failedCount > 0 && <span className="text-[var(--error)]">✕ {failedCount} failed</span>}
            </div>
          </div>

          <div
            className="rounded-lg border border-default divide-y divide-[var(--border-default)] overflow-hidden"
            style={{ backgroundColor: "var(--bg-secondary)" }}
          >
            {queue.map((item) => (
              <div key={item.id} className="flex items-center gap-4 px-4 py-3">
                <FileImage className="w-5 h-5 flex-shrink-0" style={{ color: "var(--text-tertiary)" }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                    {item.file.name}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {formatFileSize(item.file.size)}
                    </span>
                    {item.status === "queued" && (
                      <span className="text-[10px] font-extrabold uppercase bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded border border-zinc-700">
                        Queued
                      </span>
                    )}
                    {item.status === "uploading" && (
                      <span className="text-[10px] font-extrabold uppercase bg-amber-950/40 text-amber-400 px-2 py-0.5 rounded border border-amber-900/30 animate-pulse">
                        Uploading
                      </span>
                    )}
                    {item.status === "polling" && (
                      <span className="text-[10px] font-extrabold uppercase bg-blue-950/40 text-blue-400 px-2 py-0.5 rounded border border-blue-900/30">
                        Processing
                      </span>
                    )}
                    {item.status === "done" && (
                      <span className="text-[10px] font-extrabold uppercase bg-emerald-950/40 text-emerald-400 px-2 py-0.5 rounded border border-emerald-900/30">
                        Ready
                      </span>
                    )}
                    {item.status === "duplicate" && (
                      <span className="text-[10px] font-extrabold uppercase bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded border border-zinc-700">
                        Already in Gallery
                      </span>
                    )}
                    {item.status === "error" && (
                      <span className="text-[10px] font-extrabold uppercase bg-rose-950/40 text-rose-400 px-2 py-0.5 rounded border border-rose-900/30">
                        Failed
                      </span>
                    )}
                    {item.error && (
                      <span
                        className="text-xs font-medium"
                        style={{ color: item.status === "duplicate" ? "var(--text-secondary)" : "var(--error)" }}
                      >
                        {item.error}
                      </span>
                    )}
                  </div>

                  {/* Individual active progress bar */}
                  {(item.status === "uploading" || item.status === "polling") && (
                    <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          item.status === "polling" ? "animate-pulse" : ""
                        }`}
                        style={{
                          width: `${item.progress}%`,
                          backgroundColor: item.status === "polling" ? "var(--brand)" : "var(--accent-primary)",
                        }}
                      />
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {(item.status === "done" || (item.status === "duplicate" && item.assetId)) && item.assetId && (
                    <Link
                      href={`/media/${item.assetId}`}
                      className="p-1.5 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
                      title="View photo"
                    >
                      <Eye className="w-4 h-4" style={{ color: "var(--text-secondary)" }} />
                    </Link>
                  )}
                  {item.status === "error" && (
                    <button
                      onClick={() => handleRetry(item.id)}
                      className="p-1.5 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
                      title="Retry upload"
                    >
                      <RotateCw className="w-4 h-4" style={{ color: "var(--warning)" }} />
                    </button>
                  )}
                  <button
                    onClick={() => removeItem(item.id)}
                    className="p-1.5 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
                    title="Remove from queue"
                  >
                    <X className="w-4 h-4" style={{ color: "var(--text-tertiary)" }} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Floating Toast */}
      {toast && (
        <div
          className="fixed bottom-20 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl border border-default shadow-lg transition-all duration-300 animate-slide-in"
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
