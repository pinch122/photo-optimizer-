"use client";

import { useState, useCallback, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { uploadMedia, getMediaStatus } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import { Upload, CloudUpload, FileImage, X, RotateCw, Eye } from "lucide-react";
import Link from "next/link";
import type { AssetStatus } from "@/lib/types";

interface QueueItem {
  id: string;
  file: File;
  status: "queued" | "uploading" | "polling" | "done" | "error";
  assetId?: string;
  assetStatus?: AssetStatus;
  error?: string;
  progress: number;
}

export default function UploadPage() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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
          } else if (status.status === "FAILED") {
            updateItem(queueId, { status: "error", assetStatus: "FAILED", error: status.error_message || "Processing failed" });
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

  const uploadMutation = useMutation({
    mutationFn: async (item: QueueItem) => {
      updateItem(item.id, { status: "uploading", progress: 50 });
      const result = await uploadMedia(item.file);
      updateItem(item.id, { status: "polling", assetId: result.id, assetStatus: result.status, progress: 75 });
      pollStatus(item.id, result.id);
      return result;
    },
    onError: (error: Error, item: QueueItem) => {
      const msg = error.message.includes("409") ? "Duplicate file already exists" : error.message;
      updateItem(item.id, { status: "error", error: msg, progress: 0 });
    },
  });

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
      newItems.forEach((item) => uploadMutation.mutate(item));
    },
    [uploadMutation]
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

  const successCount = queue.filter((i) => i.status === "done").length;
  const processingCount = queue.filter((i) => ["uploading", "polling", "queued"].includes(i.status)).length;
  const errorCount = queue.filter((i) => i.status === "error").length;

  return (
    <>
      <PageHeader title="Upload Photos" description="Add new photos to your PhotoMind AI library" />

      {/* Drop Zone */}
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

      {/* Upload Queue */}
      {queue.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
              Upload Queue ({queue.length} files)
            </h2>
            <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-secondary)" }}>
              {successCount > 0 && <span className="text-[var(--success)]">✓ {successCount} ready</span>}
              {processingCount > 0 && <span className="text-[var(--warning)]">⏳ {processingCount} processing</span>}
              {errorCount > 0 && <span className="text-[var(--error)]">✕ {errorCount} failed</span>}
            </div>
          </div>

          <div
            className="rounded-lg border border-default divide-y divide-[var(--border-default)]"
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
                    {item.assetStatus && <StatusBadge status={item.assetStatus} />}
                    {item.error && (
                      <span className="text-xs" style={{ color: "var(--error)" }}>{item.error}</span>
                    )}
                  </div>
                  {/* Progress bar */}
                  {(item.status === "uploading" || item.status === "polling") && (
                    <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          item.status === "polling" ? "animate-pulse" : ""
                        }`}
                        style={{
                          width: `${item.progress}%`,
                          backgroundColor: "var(--accent-primary)",
                        }}
                      />
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {item.status === "done" && item.assetId && (
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
                      onClick={() => uploadMutation.mutate(item)}
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
    </>
  );
}
