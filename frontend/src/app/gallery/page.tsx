"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl } from "@/lib/api";
import { formatFileSize, formatRelativeTime } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import { Filter, ArrowUpDown, CheckSquare, Square, Loader2 } from "lucide-react";
import type { AssetStatus } from "@/lib/types";

type SortBy = "newest" | "oldest" | "largest" | "name";

export default function GalleryPage() {
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "ALL">("ALL");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [allItems, setAllItems] = useState<any[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const observerRef = useRef<HTMLDivElement>(null);
  const limit = 30;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["gallery", offset],
    queryFn: () => searchMedia("photo", limit, offset),
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

  // Filter and sort
  let filtered = allItems;
  if (statusFilter !== "ALL") {
    filtered = filtered.filter((i) => i.status === statusFilter);
  }
  filtered = [...filtered].sort((a, b) => {
    switch (sortBy) {
      case "newest": return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case "oldest": return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case "largest": return b.file_size - a.file_size;
      case "name": return a.filename.localeCompare(b.filename);
      default: return 0;
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
              onClick={() => { setSelectMode(!selectMode); setSelected(new Set()); }}
              className={`h-8 px-3 rounded-md border text-xs font-medium transition-colors duration-150 ${
                selectMode ? "border-brand text-brand bg-brand/10" : "border-default hover:border-[var(--border-subtle)]"
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
          <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>No photos yet</p>
          <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>Upload your first photos to get started</p>
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
                  className={`group relative aspect-square rounded-lg overflow-hidden border transition-all duration-200 hover:shadow-md hover:scale-[1.02] ${
                    isSelected ? "border-brand ring-2 ring-brand/30" : "border-default"
                  }`}
                  style={{ backgroundColor: "var(--bg-tertiary)" }}
                  onClick={() => selectMode && toggleSelect(item.id)}
                >
                  {selectMode ? (
                    <button className="absolute top-2 left-2 z-10">
                      {isSelected ? (
                        <CheckSquare className="w-5 h-5 text-brand" />
                      ) : (
                        <Square className="w-5 h-5" style={{ color: "var(--text-tertiary)" }} />
                      )}
                    </button>
                  ) : (
                    <Link href={`/media/${item.id}`} className="absolute inset-0 z-10" />
                  )}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {/* Hover overlay */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all duration-200 flex items-end pointer-events-none">
                    <div className="w-full p-2 translate-y-full group-hover:translate-y-0 transition-transform duration-200">
                      <p className="text-[11px] font-medium text-white truncate">{item.filename}</p>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-[10px] text-zinc-300">{formatFileSize(item.file_size)}</span>
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
    </>
  );
}
