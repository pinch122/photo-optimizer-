"use client";

import Link from "next/link";
import { getThumbnailUrl } from "@/lib/api";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatRelativeTime } from "@/lib/utils";
import type { SearchResult } from "@/lib/types";
import { ArrowRight } from "lucide-react";

interface RecentUploadsProps {
  items: SearchResult[];
  loading?: boolean;
}

export default function RecentUploads({ items, loading = false }: RecentUploadsProps) {
  if (loading) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="w-32 h-5 rounded skeleton" />
          <div className="w-16 h-4 rounded skeleton" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="aspect-square rounded-lg skeleton" />
          ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
          Recent Uploads
        </h2>
        <div
          className="rounded-lg border border-default p-8 text-center"
          style={{ backgroundColor: "var(--bg-secondary)" }}
        >
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            No photos uploaded yet. Start by uploading your first photos.
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-1.5 mt-3 text-sm font-medium text-brand hover:text-brand-hover transition-colors"
          >
            Upload Photos <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Recent Uploads
        </h2>
        <Link
          href="/gallery"
          className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover transition-colors"
        >
          View All <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/media/${item.id}`}
            className="group relative aspect-square rounded-lg overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
            style={{ backgroundColor: "var(--bg-tertiary)" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getThumbnailUrl(item.id)}
              alt={item.filename}
              className="w-full h-full object-cover transition-opacity duration-300"
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
            {/* Overlay on hover */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all duration-200 flex items-end">
              <div className="w-full p-2 translate-y-full group-hover:translate-y-0 transition-transform duration-200">
                <p className="text-[11px] font-medium text-white truncate">{item.filename}</p>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-[10px] text-zinc-300">{formatRelativeTime(item.created_at)}</span>
                  <StatusBadge status={item.status} />
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
