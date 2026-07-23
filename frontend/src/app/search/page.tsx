"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl } from "@/lib/api";
import { formatFileSize, scoreToPercent } from "@/lib/utils";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import { Search as SearchIcon, Loader2, Clock, Trash2, History, X, Sparkles } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";

const DYNAMIC_CATEGORY_SUGGESTIONS = [
  { name: "Beaches", query: "beach" },
  { name: "Vehicles", query: "car" },
  { name: "Mountains", query: "mountain" },
  { name: "Food", query: "food" },
  { name: "College", query: "college" },
  { name: "Documents", query: "document" },
  { name: "Receipts", query: "receipt" },
  { name: "Sunset", query: "sunset" },
];

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const initialQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQuery);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ── History ─────────────────────────────────────────────────────────
  useEffect(() => {
    try {
      const stored = localStorage.getItem("photomind_recent_searches");
      if (stored) setRecentSearches(JSON.parse(stored));
    } catch (e) {
      console.error("Failed to load search history", e);
    }
  }, []);

  const saveSearchToHistory = useCallback((term: string) => {
    if (!term) return;
    setRecentSearches((prev) => {
      const next = [term, ...prev.filter((t) => t !== term)].slice(0, 5);
      try { localStorage.setItem("photomind_recent_searches", JSON.stringify(next)); }
      catch (e) { console.error("Failed to save search history", e); }
      return next;
    });
  }, []);

  const clearHistory = () => {
    setRecentSearches([]);
    try { localStorage.removeItem("photomind_recent_searches"); }
    catch (e) { console.error("Failed to clear search history", e); }
  };

  // ── Unified Search Fetch ─────────────────────────────────────────────
  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["search", searchQuery],
    queryFn: async () => {
      const start = performance.now();
      setStartTime(start);
      const result = await searchMedia(searchQuery, 24, 0);
      setLatency(Math.round(performance.now() - start));
      saveSearchToHistory(searchQuery);
      return result;
    },
    enabled: searchQuery.length > 0,
    staleTime: 0,
    gcTime: 5 * 60 * 1000,
  });

  // ── Derived state for Unified Single-Grid Layout ──────────────────────
  const items = data?.items ?? [];
  const hasResults = items.length > 0;

  // ── Handlers ─────────────────────────────────────────────────────────
  const handleSearch = useCallback(() => {
    const trimmed = query.trim();
    if (trimmed) {
      setSearchQuery(trimmed);
      router.push(`/search?q=${encodeURIComponent(trimmed)}`, { scroll: false });
    }
  }, [query, router]);

  const handleClearSearch = useCallback(() => {
    setQuery("");
    setSearchQuery("");
    router.push("/search", { scroll: false });
  }, [router]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
    if (e.key === "Escape") {
      handleClearSearch();
      inputRef.current?.blur();
    }
  };

  // Sync state with URL parameter changes
  const urlQuery = searchParams.get("q");
  useEffect(() => {
    if (urlQuery !== null && urlQuery !== searchQuery) {
      setQuery(urlQuery);
      setSearchQuery(urlQuery);
    }
  }, [urlQuery, searchQuery]);

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

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <>
      {/* Hero Search Section */}
      <div className="text-center pt-8 pb-6">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-2" style={{ color: "var(--text-primary)" }}>
          <span className="text-brand">🔍</span> PhotoMind Search
        </h1>
        <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
          Search your memories using unified multimodal understanding
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
              {query && (
                <button
                  onClick={handleClearSearch}
                  className="p-1 rounded-full hover:bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] transition-colors"
                  title="Clear search"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
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

        {/* Recent Searches */}
        {recentSearches.length > 0 && (
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4 max-w-2xl mx-auto">
            <span className="text-xs flex items-center gap-1" style={{ color: "var(--text-tertiary)" }}>
              <History className="w-3.5 h-3.5" /> Recent:
            </span>
            {recentSearches.map((term) => (
              <button
                key={term}
                onClick={() => {
                  setQuery(term);
                  setSearchQuery(term);
                  router.push(`/search?q=${encodeURIComponent(term)}`, { scroll: false });
                }}
                className="px-2.5 py-1 rounded-md text-[11px] font-medium border border-default transition-colors duration-150 hover:border-brand/40 hover:text-brand"
                style={{
                  backgroundColor: "var(--bg-secondary)",
                  color: "var(--text-secondary)",
                }}
              >
                {term}
              </button>
            ))}
            <button
              onClick={clearHistory}
              className="p-1 rounded-md hover:bg-[var(--bg-tertiary)] hover:text-red-400 transition-colors"
              title="Clear history"
            >
              <Trash2 className="w-3.5 h-3.5 text-zinc-500" />
            </button>
          </div>
        )}

        {/* Category Suggestions */}
        <div className="flex flex-wrap items-center justify-center gap-2 mt-4 max-w-2xl mx-auto">
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Explore:</span>
          {DYNAMIC_CATEGORY_SUGGESTIONS.map((cat) => (
            <button
              key={cat.query}
              onClick={() => {
                setQuery(cat.query);
                setSearchQuery(cat.query);
                router.push(`/search?q=${encodeURIComponent(cat.query)}`, { scroll: false });
              }}
              className="px-3 py-1 rounded-full text-xs font-medium border border-default transition-colors duration-150 hover:border-brand/50 hover:text-brand"
              style={{
                backgroundColor: "var(--bg-secondary)",
                color: "var(--text-secondary)",
              }}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </div>

      {/* Search Meta Bar */}
      {searchQuery && data && hasResults && (
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-default text-sm" style={{ color: "var(--text-secondary)" }}>
          <div className="flex items-center gap-2">
            <span>
              Results for &ldquo;<span className="font-medium" style={{ color: "var(--text-primary)" }}>{searchQuery}</span>&rdquo;
            </span>
            <span>·</span>
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
              {data.total} photo{data.total === 1 ? "" : "s"} found
            </span>
          </div>
          {latency !== null && (
            <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
              <Clock className="w-3 h-3" />
              {latency}ms
            </span>
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

      {/* Error state */}
      {isError && (
        <div className="text-center py-12 max-w-md mx-auto">
          <p className="text-sm font-semibold" style={{ color: "var(--error)" }}>
            Search Engine connection failure
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            Verify Qdrant is healthy and query model is initialized.
          </p>
          <button
            onClick={() => handleSearch()}
            className="mt-4 px-3.5 py-2 rounded-md text-xs font-semibold text-white bg-brand hover:bg-brand-hover"
          >
            Retry Search
          </button>
        </div>
      )}

      {/* ── Unified Single Result Grid ───────────────────────────────────── */}
      {data && hasResults && !isLoading && !isError && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {items.map((item) => {
            const isConfirmed = item.match_type === "Confirmed";
            const percent = scoreToPercent(item.score);
            const isExpanded = expandedIds.has(item.id);

            return (
              <div
                key={item.id}
                className="group flex flex-col rounded-lg overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                <Link href={`/media/${item.id}`} className="relative aspect-square overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    className={`w-full h-full object-cover transition-opacity duration-300 ${isConfirmed ? "" : "opacity-90 group-hover:opacity-100"}`}
                    loading="lazy"
                  />
                  {/* Badge: ✓ Confirmed vs 🔍 Similar */}
                  <span
                    className={`absolute top-2 right-2 z-10 px-2 py-0.5 rounded text-[10px] font-extrabold shadow-sm backdrop-blur-md ${
                      isConfirmed
                        ? "bg-brand text-white border border-brand-hover"
                        : "bg-[var(--bg-tertiary)] border border-default text-[var(--text-secondary)]"
                    }`}
                  >
                    {isConfirmed ? "✓ Confirmed" : "🔍 Similar"}
                  </span>
                </Link>

                <div className="p-3 flex-1 flex flex-col justify-between">
                  <div>
                    <Link href={`/media/${item.id}`}>
                      <p className="text-xs font-medium truncate hover:text-brand transition-colors cursor-pointer" style={{ color: "var(--text-primary)" }}>
                        {item.filename}
                      </p>
                    </Link>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${percent}%`,
                            background: isConfirmed
                              ? "linear-gradient(90deg, var(--accent-primary), var(--accent-hover))"
                              : "var(--text-tertiary)",
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-2">
                    <div className="flex items-center justify-between text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                      <span>{formatFileSize(item.file_size)}</span>
                      <span>Score: {item.score.toFixed(3)}</span>
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--border-default)]">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          toggleExpanded(item.id);
                        }}
                        className="inline-flex items-center gap-0.5 px-2 py-1 rounded text-[10px] font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        ⓘ Why?
                      </button>
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                </div>

                {isExpanded && item.explanation && item.explanation.length > 0 && (
                  <div className="p-3 border-t border-default bg-[var(--bg-tertiary)] space-y-2 text-left">
                    <p className="text-[10px] font-bold" style={{ color: "var(--text-primary)" }}>
                      Why this matched ({isConfirmed ? "Confirmed Match" : "Semantic Match"})
                    </p>
                    <div className="space-y-1">
                      {item.explanation.map((exp: string, idx: number) => (
                        <div key={idx} className="flex items-start gap-1 text-[10px]" style={{ color: "var(--text-secondary)" }}>
                          <span className={isConfirmed ? "text-[var(--success)] font-bold" : "text-[var(--text-tertiary)]"}>
                            {isConfirmed ? "✓" : "•"}
                          </span>
                          <span>{exp}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* True Empty State */}
      {data && !hasResults && searchQuery && !isLoading && !isFetching && !isError && (
        <div
          className="max-w-xl mx-auto my-10 p-8 rounded-3xl border border-default text-center space-y-6 shadow-2xl relative overflow-hidden transition-all"
          style={{
            backgroundColor: "var(--bg-secondary)",
            backgroundImage: "radial-gradient(circle at 50% 0%, var(--brand-glow) 0%, transparent 70%)"
          }}
        >
          <div className="w-16 h-16 rounded-2xl bg-brand/10 text-brand border border-brand/20 flex items-center justify-center mx-auto shadow-inner">
            <SearchIcon className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl sm:text-2xl font-black tracking-tight" style={{ color: "var(--text-primary)" }}>
              No photos matching &ldquo;<span className="text-brand">{searchQuery}</span>&rdquo;
            </h2>
            <p className="text-xs sm:text-sm leading-relaxed max-w-md mx-auto" style={{ color: "var(--text-secondary)" }}>
              PhotoMind searched your library but couldn&apos;t find any relevant photos for &ldquo;{searchQuery}&rdquo;.
            </p>
          </div>

          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-[var(--bg-tertiary)] border border-default text-[var(--text-secondary)] shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>AI search completed</span>
            <span className="text-[var(--text-tertiary)]">·</span>
            <span>No matches found</span>
            {latency !== null && (
              <>
                <span className="text-[var(--text-tertiary)]">·</span>
                <span className="text-[var(--text-tertiary)]">{latency}ms</span>
              </>
            )}
          </div>

          <div className="pt-2">
            <button
              onClick={handleClearSearch}
              className="px-6 py-2.5 rounded-xl text-xs font-extrabold text-white bg-brand hover:bg-brand-hover shadow-lg shadow-brand/20 transition-all transform hover:scale-[1.02] active:scale-95 flex items-center gap-2 mx-auto"
            >
              <X className="w-4 h-4" /> Clear Search
            </button>
          </div>

          <div className="pt-6 border-t border-default space-y-3">
            <p className="text-xs font-semibold flex items-center justify-center gap-1.5" style={{ color: "var(--text-tertiary)" }}>
              <Sparkles className="w-3.5 h-3.5 text-brand" /> Suggested searches based on your library:
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {DYNAMIC_CATEGORY_SUGGESTIONS.map((cat) => (
                <button
                  key={cat.query}
                  onClick={() => {
                    setQuery(cat.query);
                    setSearchQuery(cat.query);
                    router.push(`/search?q=${encodeURIComponent(cat.query)}`, { scroll: false });
                  }}
                  className="px-3.5 py-1.5 rounded-xl text-xs font-bold border border-default bg-[var(--bg-tertiary)] hover:bg-[var(--bg-primary)] hover:border-brand/50 hover:text-brand transition-all shadow-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>
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
