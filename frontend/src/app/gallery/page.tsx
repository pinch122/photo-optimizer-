"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listMedia, getThumbnailUrl, deleteMedia } from "@/lib/api";
import { formatFileSize, formatDate } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import { CheckSquare, Square, Loader2, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import type { AssetStatus } from "@/lib/types";

type SortBy = "newest" | "oldest" | "largest" | "name";

export default function GalleryPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "ALL">("ALL");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [allItems, setAllItems] = useState<any[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [photoToDelete, setPhotoToDelete] = useState<any | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const observerRef = useRef<HTMLDivElement>(null);
  const limit = 30;

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Use the dedicated listMedia endpoint instead of broad search
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["gallery", offset],
    queryFn: () => listMedia(limit, offset),
  });

  // Accumulate items for infinite scroll
  useEffect(() => {
    if (data?.items) {
      setAllItems((prev) => {
        if (offset === 0) return data.items;
        const existingIds = new Set(prev.map((i) => i.id));
        const newItems = data.items.filter((i: any) => !existingIds.has(i.id));
        return [...prev, ...newItems];
      });
      setHasMore(data.items.length === limit);
    }
  }, [data, offset]);

  // Intersection observer for infinite scroll
  useEffect(() => {
    if (!observerRef.current || !hasMore || isFetching) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isFetching) {
          setOffset((prev) => prev + limit);
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(observerRef.current);
    return () => observer.disconnect();
  }, [hasMore, isFetching]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDelete = async () => {
    if (!photoToDelete) return;
    setIsDeleting(true);
    try {
      await deleteMedia(photoToDelete.id);
      
      // Remove immediately from UI state
      setAllItems((prev) => prev.filter((item) => item.id !== photoToDelete.id));
      setToast({ message: "Photo deleted successfully.", type: "success" });
      setPhotoToDelete(null);

      // Invalidate queries to refresh lists
      queryClient.invalidateQueries({ queryKey: ["gallery"] });
      queryClient.invalidateQueries({ queryKey: ["recent-uploads"] });
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to delete photo.";
      setToast({ message: `Failed to delete photo: ${msg}`, type: "error" });
    } finally {
      setIsDeleting(false);
    }
  };

  // Filter and sort
  let filtered = allItems;
  if (statusFilter !== "ALL") {
    filtered = filtered.filter((i) => i.status === statusFilter);
  }
  filtered = [...filtered].sort((a, b) => {
    switch (sortBy) {
      case "newest":
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case "oldest":
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case "largest":
        return b.file_size - a.file_size;
      case "name":
        return a.filename.localeCompare(b.filename);
      default:
        return 0;
    }
  });

  return (
    <>
      <PageHeader
        title="Gallery"
        description={data ? `${data.total} photos in your library` : "Loading..."}
        actions={
          <div className="flex items-center gap-2">
            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as AssetStatus | "ALL")}
              className="h-8 px-2 rounded-md border border-default text-xs"
              style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}
            >
              <option value="ALL">All Status</option>
              <option value="READY">Ready</option>
              <option value="PROCESSING">Processing</option>
              <option value="FAILED">Failed</option>
            </select>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="h-8 px-2 rounded-md border border-default text-xs"
              style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="largest">Largest</option>
              <option value="name">Name A–Z</option>
            </select>

            {/* Select Toggle */}
            <button
              onClick={() => {
                setSelectMode(!selectMode);
                setSelected(new Set());
              }}
              className={`h-8 px-3 rounded-md border text-xs font-medium transition-colors duration-150 ${
                selectMode
                  ? "border-brand text-brand bg-brand/10"
                  : "border-default hover:border-[var(--border-subtle)]"
              }`}
              style={{ color: selectMode ? undefined : "var(--text-secondary)" }}
            >
              {selectMode ? "Cancel" : "Select"}
            </button>
          </div>
        }
      />

      {/* Grid */}
      {isLoading && allItems.length === 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {Array.from({ length: 15 }).map((_, i) => (
            <div key={i} className="aspect-square rounded-lg skeleton" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>
            No photos yet
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>
            Upload your first photos to get started
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-md text-sm font-medium text-white bg-brand hover:bg-brand-hover transition-colors"
          >
            Upload Photos
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {filtered.map((item) => {
              const isSelected = selected.has(item.id);
              return (
                <div
                  key={item.id}
                  className={`group relative aspect-square rounded-lg overflow-hidden border transition-all duration-200 hover:shadow-md hover:scale-[1.02] cursor-pointer ${
                    isSelected ? "border-brand ring-2 ring-brand/30" : "border-default"
                  }`}
                  style={{ backgroundColor: "var(--bg-tertiary)" }}
                  onClick={() => selectMode && toggleSelect(item.id)}
                >
                  {selectMode ? (
                    <button className="absolute top-2 left-2 z-10" aria-label="Select photo">
                      {isSelected ? (
                        <CheckSquare className="w-5 h-5 text-brand" />
                      ) : (
                        <Square className="w-5 h-5" style={{ color: "var(--text-tertiary)" }} />
                      )}
                    </button>
                  ) : (
                    <>
                      <Link href={`/media/${item.id}`} className="absolute inset-0 z-10" />
                      {/* Trash Delete button on hover */}
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setPhotoToDelete(item);
                        }}
                        className="absolute top-2 right-2 z-20 p-1.5 rounded-md bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-155 hover:bg-red-600 hover:text-white"
                        title="Delete photo"
                        aria-label="Delete photo"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {/* Hover overlay details */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/45 transition-all duration-200 flex items-end pointer-events-none">
                    <div className="w-full p-2 translate-y-full group-hover:translate-y-0 transition-transform duration-200 bg-gradient-to-t from-black/80 to-transparent">
                      <p className="text-[11px] font-medium text-white truncate">{item.filename}</p>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-[9px] text-zinc-300">{formatDate(item.created_at)}</span>
                        <StatusBadge status={item.status} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Infinite scroll trigger */}
          {hasMore && (
            <div ref={observerRef} className="flex items-center justify-center py-8">
              {isFetching && <Loader2 className="w-5 h-5 animate-spin text-brand" />}
            </div>
          )}
        </>
      )}

      {/* Bulk action bar */}
      {selectMode && selected.size > 0 && (
        <div
          className="fixed bottom-16 lg:bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-4 py-2.5 rounded-xl border border-default shadow-lg"
          style={{ backgroundColor: "var(--bg-secondary)" }}
        >
          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {selected.size} selected
          </span>
          <button className="px-3 py-1 rounded-md text-xs font-medium bg-brand/10 text-brand hover:bg-brand/20 transition-colors">
            Reprocess
          </button>
          <button className="px-3 py-1 rounded-md text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors">
            Delete
          </button>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {photoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity duration-200">
          <div
            className="w-full max-w-md rounded-xl border border-default p-6 shadow-lg transform transition-all duration-200 scale-100"
            style={{ backgroundColor: "var(--bg-secondary)" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
          >
            <h3
              id="delete-dialog-title"
              className="text-lg font-semibold tracking-tight mb-2"
              style={{ color: "var(--text-primary)" }}
            >
              Delete Photo?
            </h3>
            <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
              Are you sure you want to permanently delete this photo?
            </p>
            
            <div
              className="p-3 rounded-lg text-xs space-y-1.5 mb-6 border border-default"
              style={{ backgroundColor: "var(--bg-primary)", color: "var(--text-secondary)" }}
            >
              <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                This action will also remove:
              </p>
              <ul className="list-disc pl-4 space-y-0.5" style={{ color: "var(--text-secondary)" }}>
                <li>Original image file</li>
                <li>Generated thumbnail</li>
                <li>Extracted metadata (EXIF)</li>
                <li>AI vector embedding</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                disabled={isDeleting}
                onClick={() => setPhotoToDelete(null)}
                className="px-4 py-2 rounded-lg text-sm font-medium border border-default hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                disabled={isDeleting}
                onClick={handleDelete}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-50 min-w-[80px]"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  "Delete"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

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
