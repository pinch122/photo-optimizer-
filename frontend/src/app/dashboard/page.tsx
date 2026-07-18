"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listMedia, getHealth, searchMedia, getThumbnailUrl } from "@/lib/api";
import { formatDate, formatRelativeTime } from "@/lib/utils";
import Link from "next/link";
import { 
  Search, Upload, Image, Brain, FolderOpen, Calendar, 
  ArrowRight, ChevronRight, BarChart3, Loader2 
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  // 1. Fetch recent uploads & count
  const { data: mediaData, isLoading: isLoadingRecent } = useQuery({
    queryKey: ["recent-uploads-dashboard"],
    queryFn: () => listMedia(6, 0),
  });

  const totalPhotos = mediaData?.total ?? 0;
  const recentItems = mediaData?.items ?? [];

  // 2. Fetch health / engine status
  const { data: healthData } = useQuery({
    queryKey: ["dashboard-health"],
    queryFn: getHealth,
    refetchInterval: 30000,
  });

  // 3. Fetch previews for dynamic Smart Collections cards
  const { data: beachData, isLoading: beachLoading } = useQuery({
    queryKey: ["dashboard-col", "beach"],
    queryFn: () => searchMedia("beach", 4, 0),
  });
  const { data: dogData, isLoading: dogLoading } = useQuery({
    queryKey: ["dashboard-col", "dog"],
    queryFn: () => searchMedia("dog", 4, 0),
  });
  const { data: foodData, isLoading: foodLoading } = useQuery({
    queryKey: ["dashboard-col", "food"],
    queryFn: () => searchMedia("food", 4, 0),
  });
  const { data: carData, isLoading: carLoading } = useQuery({
    queryKey: ["dashboard-col", "car"],
    queryFn: () => searchMedia("car", 4, 0),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = searchQuery.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  };

  const handleSearchExample = (example: string) => {
    router.push(`/search?q=${encodeURIComponent(example.toLowerCase())}`);
  };

  return (
    <div className="space-y-8 pb-16">
      
      {/* SECTION 1: Hero Welcome & Search */}
      <div 
        className="rounded-2xl border border-default p-6 sm:p-8 relative overflow-hidden" 
        style={{ 
          backgroundColor: "var(--bg-secondary)",
          backgroundImage: "radial-gradient(circle at 100% 0%, var(--brand-glow) 0%, transparent 60%)" 
        }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              👋 Welcome back
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              {isLoadingRecent ? (
                "Loading your memory vault..."
              ) : (
                `You have ${totalPhotos.toLocaleString()} memories ready to explore.`
              )}
            </p>
          </div>
          <Link
            href="/upload"
            className="sm:self-start inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-brand hover:bg-brand-hover transition-all duration-150 hover:scale-[1.02] shadow-sm hover:shadow-glow"
          >
            <Upload className="w-4 h-4" />
            Upload Photos
          </Link>
        </div>

        {/* Big search input */}
        <form onSubmit={handleSearchSubmit} className="relative w-full max-w-2xl">
          <div className="relative">
            <Search
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5"
              style={{ color: "var(--text-tertiary)" }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search your memories..."
              className="w-full h-12 pl-12 pr-24 rounded-xl border border-default text-sm transition-all duration-200 focus:border-brand focus:shadow-glow outline-none bg-[var(--bg-primary)]"
              style={{ color: "var(--text-primary)" }}
            />
            <button
              type="submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 h-8 px-4 rounded-lg text-xs font-semibold text-white bg-brand hover:bg-brand-hover transition-colors"
            >
              Search
            </button>
          </div>
        </form>

        {/* Examples */}
        <div className="flex flex-wrap items-center gap-2.5 mt-4 text-xs">
          <span style={{ color: "var(--text-tertiary)" }}>Try searching:</span>
          {["Beach", "Dog", "Passport", "Sunset", "Car"].map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => handleSearchExample(example)}
              className="px-2.5 py-1 rounded-md border border-default transition-all duration-150 hover:border-brand/40 hover:text-brand bg-[var(--bg-primary)]"
              style={{ color: "var(--text-secondary)" }}
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      {/* SECTION 2: Recent Uploads */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
            Recent Uploads
          </h2>
          {totalPhotos > 6 ? (
            <Link
              href="/gallery"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline transition-colors"
            >
              +{totalPhotos - 6} more <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <Link
              href="/gallery"
              className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline transition-colors"
            >
              View Gallery <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>
        
        {isLoadingRecent ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-xl skeleton animate-pulse" />
            ))}
          </div>
        ) : recentItems.length === 0 ? (
          <div className="rounded-xl border border-default p-8 text-center bg-[var(--bg-secondary)]">
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              No photos uploaded yet. Start by uploading some pictures.
            </p>
            <Link
              href="/upload"
              className="inline-flex items-center gap-1.5 mt-3 text-xs font-semibold text-brand hover:underline transition-colors"
            >
              Upload Photos <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {recentItems.map((item) => (
              <Link
                key={item.id}
                href={`/media/${item.id}`}
                className="group relative aspect-square rounded-xl overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-lg hover:scale-[1.03]"
                style={{ backgroundColor: "var(--bg-tertiary)" }}
              >
                <img
                  src={getThumbnailUrl(item.id)}
                  alt={item.filename}
                  loading="lazy"
                  className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all duration-200 flex items-end">
                  <div className="w-full p-3 translate-y-full group-hover:translate-y-0 transition-transform duration-200 bg-gradient-to-t from-black/90 to-transparent">
                    <p className="text-[10px] font-semibold text-white truncate">{item.filename}</p>
                    <span className="text-[8px] text-zinc-300">{formatRelativeTime(item.created_at)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* SECTION 3: Smart Collections Preview */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
            Smart Collections
          </h2>
          <Link
            href="/collections"
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline transition-colors"
          >
            View All Collections <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { slug: "beach", name: "Beaches", desc: "Sandy shores and ocean horizons", data: beachData, loading: beachLoading },
            { slug: "dog", name: "Dogs", desc: "Your favorite furry companions", data: dogData, loading: dogLoading },
            { slug: "food", name: "Food", desc: "Gastronomic adventures and dishes", data: foodData, loading: foodLoading },
            { slug: "car", name: "Vehicles", desc: "Cars, drives, and trips", data: carData, loading: carLoading },
          ].map((col) => {
            const hasImage = col.data && col.data.total > 0;
            const items = col.data?.items ?? [];
            return (
              <Link
                key={col.slug}
                href={`/search?q=${encodeURIComponent(col.slug)}`}
                className="group flex flex-col rounded-xl border border-default overflow-hidden transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-lg hover:scale-[1.02]"
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                <div className="relative aspect-[4/3] w-full bg-[var(--bg-tertiary)] overflow-hidden border-b border-default">
                  {col.loading ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Loader2 className="w-4 h-4 animate-spin text-brand" />
                    </div>
                  ) : !hasImage ? (
                    <div className="absolute inset-0 flex items-center justify-center text-[10px] font-medium" style={{ color: "var(--text-tertiary)" }}>
                      No preview available
                    </div>
                  ) : col.data!.total >= 4 ? (
                    <div className="grid grid-cols-2 grid-rows-2 h-full w-full gap-[1px] p-[1px]">
                      {items.slice(0, 4).map((item) => (
                        <div key={item.id} className="relative overflow-hidden w-full h-full bg-[var(--bg-secondary)]">
                          <img
                            src={getThumbnailUrl(item.id)}
                            alt={item.filename}
                            loading="lazy"
                            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <img
                      src={getThumbnailUrl(items[0].id)}
                      alt={items[0].filename}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                    />
                  )}
                </div>
                <div className="p-3 flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <h3 className="text-xs font-semibold truncate" style={{ color: "var(--text-primary)" }}>{col.name}</h3>
                      <span className="text-[9px] px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-secondary)" }}>
                        {col.loading ? "..." : `${col.data?.total ?? 0} items`}
                      </span>
                    </div>
                    <p className="text-[10px] line-clamp-2" style={{ color: "var(--text-tertiary)" }}>{col.desc}</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* SECTION 4: Quick Actions */}
      <div>
        <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              href: "/search",
              label: "Search Memories",
              description: "Find photos using natural language AI query search",
              icon: Search,
              iconColor: "var(--accent-primary)",
            },
            {
              href: "/upload",
              label: "Upload Photos",
              description: "Add new photos and scan folders for ingestion",
              icon: Upload,
              iconColor: "var(--success)",
            },
            {
              href: "/analytics",
              label: "View Analytics",
              description: "Check storage breakdown and indexing metrics",
              icon: BarChart3,
              iconColor: "var(--warning)",
            },
          ].map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="group rounded-xl border border-default p-5 transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-lg hover:scale-[1.02] flex items-center justify-between"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <div className="flex gap-4">
                <div
                  className="flex items-center justify-center w-11 h-11 rounded-xl transition-transform duration-200 group-hover:scale-105"
                  style={{ backgroundColor: `${action.iconColor}15` }}
                >
                  <action.icon className="w-5 h-5" style={{ color: action.iconColor }} />
                </div>
                <div>
                  <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    {action.label}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                    {action.description}
                  </p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-zinc-400 group-hover:translate-x-1 transition-transform" />
            </Link>
          ))}
        </div>
      </div>

      {/* SECTION 5: Library Overview */}
      {healthData && (healthData.status === "healthy" || healthData.status === "ok") && (
        <div>
          <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>
            Library Overview
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            {/* Photos */}
            <div className="rounded-xl border border-default p-5 flex items-center gap-4 animate-fadeIn" style={{ backgroundColor: "var(--bg-secondary)" }}>
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400">
                <Image className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Photos</span>
                <p className="text-lg font-bold leading-tight" style={{ color: "var(--text-primary)" }}>{totalPhotos.toLocaleString()}</p>
              </div>
            </div>

            {/* Collections */}
            <div className="rounded-xl border border-default p-5 flex items-center gap-4 animate-fadeIn" style={{ backgroundColor: "var(--bg-secondary)" }}>
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400">
                <FolderOpen className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Collections</span>
                <p className="text-lg font-bold leading-tight" style={{ color: "var(--text-primary)" }}>8 Albums</p>
              </div>
            </div>

            {/* Recent Upload Date */}
            {recentItems[0] && (
              <div className="rounded-xl border border-default p-5 flex items-center gap-4 animate-fadeIn" style={{ backgroundColor: "var(--bg-secondary)" }}>
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Recent Upload</span>
                  <p className="text-xs font-bold leading-tight mt-0.5" style={{ color: "var(--text-primary)" }}>
                    {formatDate(recentItems[0].created_at)}
                  </p>
                </div>
              </div>
            )}

            {/* AI Status */}
            <div className="rounded-xl border border-default p-5 flex items-center gap-4 animate-fadeIn" style={{ backgroundColor: "var(--bg-secondary)" }}>
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400">
                <Brain className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>AI Status</span>
                <p className="text-lg font-bold leading-tight text-emerald-400">Active</p>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
