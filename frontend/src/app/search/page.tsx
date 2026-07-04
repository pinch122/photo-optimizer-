"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl } from "@/lib/api";
import { formatFileSize, scoreToPercent } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import { Search as SearchIcon, Loader2, Clock } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";

const examplePrompts = ["sunset", "beach", "food", "mountains", "dog", "car", "flowers", "city"];

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const initialQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQuery);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [latency, setLatency] = useState<number | null>(null);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["search", searchQuery],
    queryFn: async () => {
      const start = performance.now();
      setStartTime(start);
      const result = await searchMedia(searchQuery, 24, 0);
      setLatency(Math.round(performance.now() - start));
      return result;
    },
    enabled: searchQuery.length > 0,
  });

  const handleSearch = useCallback(() => {
    const trimmed = query.trim();
    if (trimmed) {
      setSearchQuery(trimmed);
      router.push(`/search?q=${encodeURIComponent(trimmed)}`, { scroll: false });
    }
  }, [query, router]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
    if (e.key === "Escape") {
      setQuery("");
      inputRef.current?.blur();
    }
  };

  // Global ⌘K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <>
      {/* Hero Search Section */}
      <div className="text-center pt-8 pb-6">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-2" style={{ color: "var(--text-primary)" }}>
          <span className="text-brand">🔍</span> PhotoMind Search
        </h1>
        <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
          Search your memories using natural language
        </p>

        {/* Search Input */}
        <div className="relative max-w-2xl mx-auto">
          <div className="relative">
            <SearchIcon
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5"
              style={{ color: "var(--text-tertiary)" }}
            />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='Find photos of "beach sunset"...'
              className="w-full h-12 pl-12 pr-20 rounded-xl border border-default text-base transition-all duration-200 focus:border-brand focus:shadow-glow outline-none"
              style={{
                backgroundColor: "var(--bg-secondary)",
                color: "var(--text-primary)",
              }}
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
              {isFetching && <Loader2 className="w-4 h-4 animate-spin text-brand" />}
              <kbd
                className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono"
                style={{
                  backgroundColor: "var(--bg-tertiary)",
                  color: "var(--text-tertiary)",
                }}
              >
                ⌘K
              </kbd>
            </div>
          </div>
        </div>

        {/* Example Prompts */}
        {!searchQuery && (
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4 max-w-2xl mx-auto">
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Try:</span>
            {examplePrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => { setQuery(prompt); setSearchQuery(prompt); router.push(`/search?q=${prompt}`, { scroll: false }); }}
                className="px-3 py-1 rounded-full text-xs font-medium border border-default transition-colors duration-150 hover:border-brand/50 hover:text-brand"
                style={{
                  backgroundColor: "var(--bg-secondary)",
                  color: "var(--text-secondary)",
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Search Meta */}
      {searchQuery && data && (
        <div className="flex items-center gap-3 mb-4 text-sm" style={{ color: "var(--text-secondary)" }}>
          <span>
            Results for &ldquo;<span className="font-medium" style={{ color: "var(--text-primary)" }}>{searchQuery}</span>&rdquo;
          </span>
          <span>·</span>
          <span>{data.total} photos</span>
          {latency !== null && (
            <>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {latency}ms
              </span>
            </>
          )}
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && searchQuery && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-lg overflow-hidden">
              <div className="aspect-square skeleton" />
              <div className="p-3 space-y-2" style={{ backgroundColor: "var(--bg-secondary)" }}>
                <div className="w-3/4 h-3 rounded skeleton" />
                <div className="w-1/2 h-2 rounded skeleton" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Results Grid */}
      {data && data.items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {data.items.map((item) => {
            const percent = scoreToPercent(item.score);
            return (
              <Link
                key={item.id}
                href={`/media/${item.id}`}
                className="group rounded-lg overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                <div className="relative aspect-square overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    className="w-full h-full object-cover transition-opacity duration-300"
                    loading="lazy"
                  />
                </div>
                <div className="p-3">
                  <p className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
                    {item.filename}
                  </p>
                  {/* Score bar */}
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${percent}%`,
                          background: percent >= 80
                            ? "linear-gradient(90deg, var(--accent-primary), var(--accent-hover))"
                            : percent >= 50
                            ? "var(--accent-primary)"
                            : "var(--text-tertiary)",
                        }}
                      />
                    </div>
                    <span className="text-[11px] font-mono font-medium flex-shrink-0" style={{ color: "var(--text-secondary)" }}>
                      {percent}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                      {formatFileSize(item.file_size)}
                    </span>
                    <StatusBadge status={item.status} />
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* No Results */}
      {data && data.items.length === 0 && searchQuery && (
        <div className="text-center py-16">
          <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>
            No photos match this description
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>
            Try different words or upload more photos
          </p>
        </div>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <div className="text-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-brand mx-auto mb-4" />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading Search Engine...</p>
      </div>
    }>
      <SearchContent />
    </Suspense>
  );
}
