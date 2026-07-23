"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getTrashMedia,
  restoreMedia,
  permanentlyDeleteMedia,
  emptyTrash,
  bulkRestoreTrash,
  bulkPermanentlyDeleteTrash,
  getThumbnailUrl,
} from "@/lib/api";
import { MediaAsset } from "@/lib/types";
import { formatFileSize, formatDate } from "@/lib/utils";
import {
  Trash2,
  RotateCcw,
  AlertTriangle,
  Loader2,
  CheckSquare,
  Square,
  Info,
} from "lucide-react";

export default function RecycleBinPage() {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeModal, setActiveModal] = useState<"single_perm" | "bulk_perm" | "empty" | null>(null);
  const [targetAsset, setTargetAsset] = useState<MediaAsset | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["trash-media"],
    queryFn: () => getTrashMedia(),
  });

  const trashItems = data?.items ?? [];
  const totalTrashSize = trashItems.reduce((sum, item) => sum + item.file_size, 0);

  const showToast = (message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const refreshAllQueries = (restoredIds?: string[]) => {
    if (restoredIds && restoredIds.length > 0) {
      try {
        const stored = localStorage.getItem("photomind_kept_recommendations");
        if (stored) {
          const keptArr: string[] = JSON.parse(stored);
          const filtered = keptArr.filter((id) => !restoredIds.includes(id));
          localStorage.setItem("photomind_kept_recommendations", JSON.stringify(filtered));
        }
      } catch (e) {
        console.error("Failed to clean restored IDs from kept recommendations", e);
      }
    }
    queryClient.invalidateQueries({ queryKey: ["trash-media"] });
    queryClient.invalidateQueries({ queryKey: ["trash-count"] });
    queryClient.invalidateQueries({ queryKey: ["media-list"] });
    queryClient.invalidateQueries({ queryKey: ["gallery"] });
    queryClient.invalidateQueries({ queryKey: ["recent-uploads"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations-all-media"] });
    queryClient.invalidateQueries({ queryKey: ["collection-preview"] });
    queryClient.invalidateQueries({ queryKey: ["search"] });
    queryClient.invalidateQueries({ queryKey: ["similar-media"] });
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedIds.size === trashItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(trashItems.map((item) => item.id)));
    }
  };

  const handleSingleRestore = async (id: string) => {
    setIsProcessing(true);
    try {
      await restoreMedia(id);
      showToast("Photo restored successfully");
      refreshAllQueries([id]);
    } catch (e) {
      showToast("Failed to restore photo", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkRestore = async () => {
    if (selectedIds.size === 0) return;
    setIsProcessing(true);
    try {
      const ids = Array.from(selectedIds);
      await bulkRestoreTrash(ids);
      showToast(`Restored ${ids.length} photos`);
      setSelectedIds(new Set());
      refreshAllQueries(ids);
    } catch (e) {
      showToast("Failed to restore selected photos", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const confirmSinglePermanentDelete = async () => {
    if (!targetAsset) return;
    setIsProcessing(true);
    try {
      await permanentlyDeleteMedia(targetAsset.id);
      showToast("Photo permanently deleted");
      setActiveModal(null);
      setTargetAsset(null);
      refreshAllQueries();
    } catch (e) {
      showToast("Failed to permanently delete photo", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const confirmBulkPermanentDelete = async () => {
    if (selectedIds.size === 0) return;
    setIsProcessing(true);
    try {
      const ids = Array.from(selectedIds);
      await bulkPermanentlyDeleteTrash(ids);
      showToast(`Permanently deleted ${ids.length} photos`);
      setSelectedIds(new Set());
      setActiveModal(null);
      refreshAllQueries();
    } catch (e) {
      showToast("Failed to permanently delete selected photos", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const confirmEmptyTrash = async () => {
    setIsProcessing(true);
    try {
      const res = await emptyTrash();
      showToast(res.message || "Recycle bin emptied");
      setSelectedIds(new Set());
      setActiveModal(null);
      refreshAllQueries();
    } catch (e) {
      showToast("Failed to empty Recycle Bin", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-brand mb-4" />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Loading Recycle Bin...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl shadow-xl border border-default bg-[var(--bg-secondary)] flex items-center gap-3 animate-fadeIn">
          <div className={`w-2.5 h-2.5 rounded-full ${toast.type === "error" ? "bg-rose-500" : "bg-emerald-500"}`} />
          <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{toast.message}</span>
        </div>
      )}

      {/* Header Banner */}
      <div
        className="rounded-2xl border border-default p-6 sm:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-6"
        style={{
          backgroundColor: "var(--bg-secondary)",
          backgroundImage: "radial-gradient(circle at 100% 0%, var(--brand-glow) 0%, transparent 60%)",
        }}
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2.5" style={{ color: "var(--text-primary)" }}>
            <Trash2 className="w-7 h-7 text-rose-400" /> Recycle Bin
          </h1>
          <p className="text-sm mt-1.5 max-w-xl leading-relaxed flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
            <Info className="w-4 h-4 text-brand flex-shrink-0" />
            Deleted photos appear here. Photos are permanently removed after 30 days.
          </p>
        </div>

        {trashItems.length > 0 && (
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="p-4 rounded-xl border border-default bg-[var(--bg-primary)] flex flex-col items-center justify-center min-w-[130px] shadow-sm">
              <span className="text-[10px] uppercase font-bold tracking-wider" style={{ color: "var(--text-tertiary)" }}>Trash Size</span>
              <p className="text-xl font-black mt-0.5 text-rose-400">{formatFileSize(totalTrashSize)}</p>
            </div>

            <button
              onClick={() => setActiveModal("empty")}
              disabled={isProcessing}
              className="px-4 py-2.5 rounded-xl text-xs font-extrabold bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all shadow-sm flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" /> Empty Recycle Bin
            </button>
          </div>
        )}
      </div>

      {/* Controls Bar for Bulk Selection */}
      {trashItems.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl border border-default bg-[var(--bg-secondary)]">
          <button
            onClick={handleSelectAll}
            className="flex items-center gap-2 text-xs font-bold"
            style={{ color: "var(--text-primary)" }}
          >
            {selectedIds.size === trashItems.length ? (
              <CheckSquare className="w-4 h-4 text-brand" />
            ) : (
              <Square className="w-4 h-4 text-[var(--text-tertiary)]" />
            )}
            Select All ({trashItems.length})
          </button>

          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 animate-fadeIn">
              <button
                onClick={handleBulkRestore}
                disabled={isProcessing}
                className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-brand/10 hover:bg-brand/20 text-brand border border-brand/30 flex items-center gap-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Restore Selected ({selectedIds.size})
              </button>

              <button
                onClick={() => setActiveModal("bulk_perm")}
                disabled={isProcessing}
                className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete Selected Permanently ({selectedIds.size})
              </button>
            </div>
          )}
        </div>
      )}

      {/* Recycle Bin Items Grid */}
      {trashItems.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {trashItems.map((item) => {
            const isSelected = selectedIds.has(item.id);
            const remainingDays = item.remaining_days ?? 30;

            return (
              <div
                key={item.id}
                className={`group relative rounded-2xl border transition-all duration-200 overflow-hidden flex flex-col justify-between ${
                  isSelected ? "border-brand shadow-lg ring-1 ring-brand" : "border-default hover:border-[var(--border-subtle)]"
                }`}
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                {/* Checkbox Overlay */}
                <button
                  onClick={() => handleToggleSelect(item.id)}
                  className="absolute top-3 left-3 z-20 p-1 rounded-md bg-black/50 backdrop-blur-md text-white transition-opacity"
                >
                  {isSelected ? <CheckSquare className="w-4 h-4 text-brand" /> : <Square className="w-4 h-4" />}
                </button>

                {/* Remaining Days Badge */}
                <div className="absolute top-3 right-3 z-20 px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/80 backdrop-blur-md text-white shadow-sm flex items-center gap-1">
                  <span>{remainingDays} days remaining</span>
                </div>

                {/* Image Thumbnail */}
                <div className="relative w-full aspect-video bg-[var(--bg-tertiary)] overflow-hidden">
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                    loading="lazy"
                  />
                </div>

                {/* Card Info */}
                <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                  <div>
                    <h3 className="text-xs font-bold truncate" style={{ color: "var(--text-primary)" }} title={item.filename}>
                      {item.filename}
                    </h3>
                    <div className="flex items-center justify-between text-[10px] mt-1" style={{ color: "var(--text-tertiary)" }}>
                      <span>{formatFileSize(item.file_size)}</span>
                      <span>Deleted {item.deleted_at ? formatDate(item.deleted_at) : "recently"}</span>
                    </div>
                  </div>

                  {/* Single Item Action Buttons */}
                  <div className="flex items-center gap-2 pt-2 border-t border-default">
                    <button
                      onClick={() => handleSingleRestore(item.id)}
                      disabled={isProcessing}
                      className="flex-1 py-1.5 rounded-lg text-xs font-bold bg-brand/10 hover:bg-brand/20 text-brand border border-brand/20 transition-colors flex items-center justify-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> Restore
                    </button>

                    <button
                      onClick={() => {
                        setTargetAsset(item);
                        setActiveModal("single_perm");
                      }}
                      disabled={isProcessing}
                      className="p-1.5 rounded-lg text-xs font-bold bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 transition-colors"
                      title="Delete Permanently"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Empty State */
        <div className="p-16 rounded-2xl border border-default text-center flex flex-col items-center justify-center min-h-[40vh]" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center mb-4 border border-rose-500/20">
            <Trash2 className="w-8 h-8 text-rose-400" />
          </div>
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>Recycle Bin is empty</h2>
          <p className="text-xs mt-1.5 max-w-sm leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
            Deleted photos appear here. Photos are permanently removed after 30 days.
          </p>
        </div>
      )}

      {/* Confirmation Modals */}
      {/* 1. Single Item Permanent Delete Modal */}
      {activeModal === "single_perm" && targetAsset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl border border-default bg-[var(--bg-secondary)] shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-extrabold" style={{ color: "var(--text-primary)" }}>Delete permanently?</h3>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Are you sure you want to permanently delete <strong className="text-white">{targetAsset.filename}</strong>? All files, metadata, and AI search indexes will be erased forever.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setActiveModal(null);
                  setTargetAsset(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={confirmSinglePermanentDelete}
                disabled={isProcessing}
                className="px-4 py-2 rounded-xl text-xs font-extrabold bg-rose-500 hover:bg-rose-600 text-white transition-colors flex items-center gap-2"
              >
                {isProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Delete Forever
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Bulk Permanent Delete Modal */}
      {activeModal === "bulk_perm" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl border border-default bg-[var(--bg-secondary)] shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-extrabold" style={{ color: "var(--text-primary)" }}>Delete selected permanently?</h3>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Are you sure you want to permanently delete <strong className="text-white">{selectedIds.size} selected photos</strong>? They will be removed forever.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={confirmBulkPermanentDelete}
                disabled={isProcessing}
                className="px-4 py-2 rounded-xl text-xs font-extrabold bg-rose-500 hover:bg-rose-600 text-white transition-colors flex items-center gap-2"
              >
                {isProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Delete Forever
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Empty Trash Modal */}
      {activeModal === "empty" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl border border-default bg-[var(--bg-secondary)] shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-extrabold" style={{ color: "var(--text-primary)" }}>Empty Recycle Bin?</h3>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              All <strong className="text-white">{trashItems.length} photos</strong> in the Recycle Bin will be permanently deleted and cannot be restored.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={confirmEmptyTrash}
                disabled={isProcessing}
                className="px-4 py-2 rounded-xl text-xs font-extrabold bg-rose-500 hover:bg-rose-600 text-white transition-colors flex items-center gap-2"
              >
                {isProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Empty Bin
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
