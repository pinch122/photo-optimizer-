"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { listMedia, getThumbnailUrl, deleteMedia } from "@/lib/api";
import { formatFileSize, formatDate } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import {
  CheckSquare,
  Square,
  Loader2,
  Trash2,
  CheckCircle2,
  AlertCircle,
  FolderPlus,
  Star,
  RotateCw,
  X,
  Check,
} from "lucide-react";
import type { AssetStatus } from "@/lib/types";

type SortBy = "newest" | "oldest" | "largest" | "name";

export default function GalleryPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "ALL">("ALL");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null);
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  // Delete modal state (single or bulk)
  const [photosToDelete, setPhotosToDelete] = useState<any[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Marquee selection refs and state
  const gridContainerRef = useRef<HTMLDivElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const isDraggingMarquee = useRef(false);
  const marqueeStartPos = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const observerRef = useRef<HTMLDivElement>(null);
  const limit = 30;

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Infinite query for gallery items
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ["gallery"],
    queryFn: ({ pageParam = 0 }) => listMedia(limit, pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const nextOffset = allPages.length * limit;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });

  const totalPhotos = data?.pages[0]?.total ?? 0;
  const allItems = data ? data.pages.flatMap((page) => page.items) : [];

  // Filter and sort items client-side
  let filtered = allItems.filter((item) => !deletedIds.has(item.id));
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

  // Intersection observer for infinite scroll
  useEffect(() => {
    if (!observerRef.current || !hasNextPage || isFetchingNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage) fetchNextPage();
      },
      { rootMargin: "200px" }
    );
    observer.observe(observerRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // ── Keyboard Shortcuts (Ctrl/Cmd+A, Escape) ────────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape -> clear selection, exit Select Mode, hide action bar
      if (e.key === "Escape") {
        if (selectMode || selected.size > 0) {
          setSelectMode(false);
          setSelected(new Set());
          setLastSelectedId(null);
        }
        return;
      }

      // Ctrl+A / Cmd+A -> Select all visible photos ONLY while Select Mode is active
      if (selectMode && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

        e.preventDefault();
        const allIds = new Set(filtered.map((item) => item.id));
        setSelected(allIds);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectMode, selected.size, filtered]);

  // ── Card Selection Toggle & Range Selection ────────────────────────────────
  const handleCardClick = useCallback(
    (e: ReactMouseEvent, item: any, index: number) => {
      if (!selectMode) return;

      const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
      const isMultiKey = isMac ? e.metaKey : e.ctrlKey;
      const isShift = e.shiftKey;

      setSelected((prev) => {
        if (isShift && lastSelectedId) {
          // Range selection: inclusive between lastSelectedId index and current index
          const next = new Set(prev);
          const lastIndex = filtered.findIndex((i) => i.id === lastSelectedId);
          if (lastIndex !== -1) {
            const start = Math.min(lastIndex, index);
            const end = Math.max(lastIndex, index);
            for (let i = start; i <= end; i++) {
              next.add(filtered[i].id);
            }
          } else {
            next.add(item.id);
          }
          return next;
        } else if (isMultiKey) {
          // Ctrl / Cmd + click: toggle individual photo without clearing
          const next = new Set(prev);
          if (next.has(item.id)) next.delete(item.id);
          else next.add(item.id);
          return next;
        } else {
          // Normal click in Select Mode: select ONLY this photo
          // If already the only selected item, clear selection
          if (prev.has(item.id) && prev.size === 1) {
            return new Set();
          }
          return new Set([item.id]);
        }
      });

      setLastSelectedId(item.id);
    },
    [selectMode, lastSelectedId, filtered]
  );

  // ── Marquee Selection Handler (RAF-Throttled 60 FPS) ────────────────────────
  const handleGridMouseDown = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      if (!selectMode) return;

      // Only respond to primary left click
      if (e.button !== 0) return;

      const target = e.target as HTMLElement;
      // Do NOT start marquee if click originated on a photo card, checkbox, or button
      if (
        target.closest("[data-card-id]") ||
        target.closest("button") ||
        target.closest("input")
      ) {
        return;
      }

      isDraggingMarquee.current = true;
      const startX = e.clientX;
      const startY = e.clientY;
      marqueeStartPos.current = { x: startX, y: startY };
      let animationFrameId: number | null = null;

      const marqueeEl = marqueeRef.current;
      if (marqueeEl) {
        marqueeEl.style.left = `${startX}px`;
        marqueeEl.style.top = `${startY}px`;
        marqueeEl.style.width = "0px";
        marqueeEl.style.height = "0px";
        marqueeEl.style.display = "block";
      }

      let dragMoved = false;

      const onMouseMove = (ev: MouseEvent) => {
        if (!isDraggingMarquee.current) return;
        const currentX = ev.clientX;
        const currentY = ev.clientY;

        const left = Math.min(startX, currentX);
        const top = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);

        if (width > 4 || height > 4) {
          dragMoved = true;
        }

        if (marqueeEl) {
          marqueeEl.style.left = `${left}px`;
          marqueeEl.style.top = `${top}px`;
          marqueeEl.style.width = `${width}px`;
          marqueeEl.style.height = `${height}px`;
        }

        // RAF-throttled real-time intersection evaluation on rendered cards only
        if (dragMoved) {
          if (animationFrameId !== null) cancelAnimationFrame(animationFrameId);
          animationFrameId = requestAnimationFrame(() => {
            const mRect = { left, top, right: left + width, bottom: top + height };
            const cardEls = document.querySelectorAll("[data-card-id]");
            const intersectedIds = new Set<string>();

            cardEls.forEach((card) => {
              const cRect = card.getBoundingClientRect();
              const intersects = !(
                cRect.right < mRect.left ||
                cRect.left > mRect.right ||
                cRect.bottom < mRect.top ||
                cRect.top > mRect.bottom
              );
              if (intersects) {
                const cardId = card.getAttribute("data-card-id");
                if (cardId) intersectedIds.add(cardId);
              }
            });

            setSelected(intersectedIds);
          });
        }
      };

      const onMouseUp = () => {
        isDraggingMarquee.current = false;
        if (animationFrameId !== null) cancelAnimationFrame(animationFrameId);
        if (marqueeEl) {
          marqueeEl.style.display = "none";
        }

        // Clicking empty space without dragging clears selection
        if (!dragMoved) {
          setSelected(new Set());
          setLastSelectedId(null);
        }

        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [selectMode]
  );

  // ── Core Delete Handler (Single or Bulk) ──────────────────────────────────
  const executeDelete = useCallback(async () => {
    if (photosToDelete.length === 0) return;
    setIsDeleting(true);
    try {
      for (const item of photosToDelete) {
        await deleteMedia(item.id, "gallery");
      }

      const deletedSet = new Set(photosToDelete.map((p) => p.id));
      setDeletedIds((prev) => new Set([...Array.from(prev), ...Array.from(deletedSet)]));

      // Remove deleted items from selected set
      setSelected((prev) => {
        const next = new Set(prev);
        deletedSet.forEach((id) => next.delete(id));
        return next;
      });

      const count = photosToDelete.length;
      setToast({
        message: count === 1 ? "Photo moved to Recycle Bin." : `${count} photos moved to Recycle Bin.`,
        type: "success",
      });
      setPhotosToDelete([]);

      // Refresh query caches
      queryClient.invalidateQueries({ queryKey: ["gallery"] });
      queryClient.invalidateQueries({ queryKey: ["recent-uploads"] });
      queryClient.invalidateQueries({ queryKey: ["trash-count"] });
      queryClient.invalidateQueries({ queryKey: ["trash-media"] });
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to delete photos.";
      setToast({ message: `Delete failed: ${msg}`, type: "error" });
    } finally {
      setIsDeleting(false);
    }
  }, [photosToDelete, queryClient]);

  // Bulk action handlers
  const handleBulkDelete = () => {
    const items = filtered.filter((i) => selected.has(i.id));
    if (items.length > 0) setPhotosToDelete(items);
  };

  const handleBulkMove = () => {
    setToast({ message: `Moved ${selected.size} photos to collection.`, type: "success" });
  };

  const handleBulkFavorite = () => {
    setToast({ message: `Favorited ${selected.size} photos.`, type: "success" });
  };

  const handleBulkReprocess = () => {
    setToast({ message: `Queued ${selected.size} photos for reprocessing.`, type: "success" });
  };

  const handleClearSelection = () => {
    setSelected(new Set());
    setLastSelectedId(null);
  };

  return (
    <>
      <PageHeader
        title="Gallery"
        description={
          isLoading ? "Loading..." : `${totalPhotos} photos in your library`
        }
        actions={
          <div className="flex items-center gap-2">
            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as AssetStatus | "ALL")}
              className="h-8 px-2 rounded-md border border-default text-xs"
              style={{
                backgroundColor: "var(--bg-secondary)",
                color: "var(--text-secondary)",
              }}
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
              style={{
                backgroundColor: "var(--bg-secondary)",
                color: "var(--text-secondary)",
              }}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="largest">Largest</option>
              <option value="name">Name A–Z</option>
            </select>

            {/* Select Toggle */}
            <button
              onClick={() => {
                if (selectMode) {
                  setSelectMode(false);
                  setSelected(new Set());
                  setLastSelectedId(null);
                } else {
                  setSelectMode(true);
                }
              }}
              className={`h-8 px-3 rounded-md border text-xs font-semibold transition-colors duration-150 ${
                selectMode
                  ? "border-blue-500 text-blue-400 bg-blue-500/10"
                  : "border-default hover:border-[var(--border-subtle)] text-[var(--text-secondary)]"
              }`}
            >
              {selectMode ? "Cancel Select" : "Select"}
            </button>
          </div>
        }
      />

      {/* Main Grid Wrapper with Marquee Mouse Down Handler */}
      <div
        ref={gridContainerRef}
        onMouseDown={handleGridMouseDown}
        className={`relative min-h-[400px] select-none ${selectMode ? "cursor-default" : ""}`}
      >
        {/* Loading state */}
        {isLoading && allItems.length === 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {Array.from({ length: 15 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-lg skeleton" />
            ))}
          </div>
        ) : filtered.length === 0 && !hasNextPage ? (
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
              {filtered.map((item, index) => {
                const isSelected = selected.has(item.id);
                return (
                  <div
                    key={item.id}
                    data-card-id={item.id}
                    className={`group relative aspect-square rounded-xl overflow-hidden transition-all duration-150 cursor-pointer ${
                      isSelected
                        ? "border-2 border-blue-500 shadow-lg scale-[1.01]"
                        : "border border-default hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.01]"
                    }`}
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                    onClick={(e) => handleCardClick(e, item, index)}
                  >
                    {/* Subtle Blue Selection Overlay (10-15%) */}
                    {isSelected && (
                      <div className="absolute inset-0 bg-blue-500/10 z-20 pointer-events-none transition-opacity duration-150" />
                    )}

                    {/* Selection Indicator Badge */}
                    {selectMode && (
                      <div className="absolute top-2.5 left-2.5 z-30 pointer-events-none">
                        {isSelected ? (
                          <div className="w-5 h-5 rounded-md bg-blue-500 text-white flex items-center justify-center shadow-md animate-scale-in">
                            <Check className="w-3.5 h-3.5 stroke-[3]" />
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-md border-2 border-white/60 bg-black/30 backdrop-blur-sm group-hover:border-white transition-colors" />
                        )}
                      </div>
                    )}

                    {/* Standard Mode: Direct Link + Hover Trash Button */}
                    {!selectMode && (
                      <>
                        <Link href={`/media/${item.id}`} className="absolute inset-0 z-10" />
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setPhotosToDelete([item]);
                          }}
                          className="absolute top-2 right-2 z-20 p-1.5 rounded-lg bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-all duration-150 hover:bg-rose-600 hover:scale-105 shadow-md"
                          title="Delete photo"
                          aria-label="Delete photo"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}

                    {/* Thumbnail Image */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={getThumbnailUrl(item.id)}
                      alt={item.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      draggable={false}
                    />

                    {/* Hover Info Overlay */}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/45 transition-all duration-200 flex items-end pointer-events-none z-10">
                      <div className="w-full p-2 translate-y-full group-hover:translate-y-0 transition-transform duration-200 bg-gradient-to-t from-black/80 to-transparent">
                        <p className="text-[11px] font-medium text-white truncate">
                          {item.filename}
                        </p>
                        <div className="flex items-center justify-between mt-0.5">
                          <span className="text-[9px] text-zinc-300">
                            {formatDate(item.created_at)}
                          </span>
                          <StatusBadge status={item.status} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Infinite Scroll Sentinel */}
            <div ref={observerRef} className="flex flex-col items-center justify-center py-8">
              {isFetchingNextPage && (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 w-full mb-8">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="aspect-square rounded-lg skeleton" />
                  ))}
                </div>
              )}
              {!hasNextPage && allItems.length > 0 && (
                <p className="text-xs font-semibold py-4" style={{ color: "var(--text-tertiary)" }}>
                  End of Library
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* ── Marquee Selection Portal Overlay (Fixed High-FPS Box) ─────────────── */}
      <div
        ref={marqueeRef}
        className="fixed pointer-events-none z-50 border border-blue-500 bg-blue-500/20 rounded-lg backdrop-blur-[1px] shadow-sm hidden"
        style={{
          boxShadow: "0 0 12px rgba(59, 130, 246, 0.3)",
          willChange: "left, top, width, height",
        }}
      />

      {/* ── Sticky Bottom Bulk Action Bar ────────────────────────────────────── */}
      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-5 py-3 rounded-2xl border border-default shadow-2xl backdrop-blur-xl bg-black/85 animate-slide-up">
          <span className="text-sm font-bold text-white pr-2 border-r border-white/10">
            {selected.size} Selected
          </span>

          {/* Move to Collection */}
          <button
            onClick={handleBulkMove}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 transition-colors"
          >
            <FolderPlus className="w-3.5 h-3.5" />
            Move to Collection
          </button>

          {/* Favorite */}
          <button
            onClick={handleBulkFavorite}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 transition-colors"
          >
            <Star className="w-3.5 h-3.5" />
            Favorite
          </button>

          {/* Reprocess */}
          <button
            onClick={handleBulkReprocess}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-purple-400 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" />
            Reprocess
          </button>

          {/* Delete Action */}
          <button
            onClick={handleBulkDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete
          </button>

          {/* Clear Selection */}
          <button
            onClick={handleClearSelection}
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold text-zinc-400 hover:text-white hover:bg-white/10 transition-colors border border-transparent hover:border-white/10"
            title="Clear selection"
          >
            <X className="w-3.5 h-3.5" />
            Clear Selection
          </button>
        </div>
      )}

      {/* ── Delete Confirmation Dialog ────────────────────────────────────── */}
      {photosToDelete.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div
            className="w-full max-w-sm rounded-2xl border border-default p-6 shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            style={{ backgroundColor: "var(--bg-secondary)" }}
          >
            {/* Preview Thumbnail(s) */}
            <div className="flex items-center gap-4 mb-4">
              {photosToDelete.length === 1 ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={getThumbnailUrl(photosToDelete[0].id)}
                  alt={photosToDelete[0].filename}
                  className="w-16 h-16 rounded-xl object-cover flex-shrink-0 border border-default"
                />
              ) : (
                <div className="w-16 h-16 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0">
                  <Trash2 className="w-7 h-7 text-rose-400" />
                </div>
              )}
              <div className="min-w-0">
                <h3
                  id="delete-dialog-title"
                  className="text-base font-bold tracking-tight"
                  style={{ color: "var(--text-primary)" }}
                >
                  {photosToDelete.length === 1 ? "Move to Recycle Bin?" : `Delete ${photosToDelete.length} photos?`}
                </h3>
                <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-tertiary)" }}>
                  {photosToDelete.length === 1
                    ? photosToDelete[0].filename
                    : `${photosToDelete.length} items selected`}
                </p>
              </div>
            </div>

            <p className="text-xs mb-5 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {photosToDelete.length === 1
                ? "This photo can be restored for 30 days before permanent deletion."
                : `These ${photosToDelete.length} photos will be moved to the Recycle Bin and can be restored for 30 days.`}
            </p>

            <div className="flex items-center justify-end gap-3">
              <button
                disabled={isDeleting}
                onClick={() => setPhotosToDelete([])}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                disabled={isDeleting}
                onClick={executeDelete}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-extrabold text-white bg-rose-500 hover:bg-rose-600 transition-colors disabled:opacity-50"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    Move to Bin
                  </>
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
            borderLeft: `4px solid ${
              toast.type === "success" ? "var(--success)" : "var(--error)"
            }`,
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
