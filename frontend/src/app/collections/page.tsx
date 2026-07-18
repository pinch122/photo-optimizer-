"use client";

import PageHeader from "@/components/layout/PageHeader";
import Link from "next/link";
import { FolderOpen, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl } from "@/lib/api";

const staticCollections = [
  { slug: "beach", name: "Beaches", description: "Sandy shores and ocean horizons" },
  { slug: "dog", name: "Dogs", description: "Your favorite furry companions" },
  { slug: "food", name: "Food", description: "Gastronomic adventures and dishes" },
  { slug: "receipt", name: "Receipts", description: "Scanned documents and bills" },
  { slug: "college", name: "College", description: "Campus days and class memories" },
  { slug: "car", name: "Vehicles", description: "Cars, drives, and trips" },
  { slug: "mountain", name: "Mountains", description: "High peaks and forest trails" },
  { slug: "document", name: "Documents", description: "Invoices, notes, and records" },
];

interface CollectionCardProps {
  slug: string;
  name: string;
  description: string;
}

function CollectionCard({ slug, name, description }: CollectionCardProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["collection-preview", slug],
    queryFn: () => searchMedia(slug, 4, 0),
    staleTime: 60000, // cache for 1 minute
  });

  const total = data?.total ?? 0;
  const items = data?.items ?? [];

  return (
    <Link
      href={`/search?q=${encodeURIComponent(slug)}`}
      className="group flex flex-col rounded-xl border border-default overflow-hidden transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-lg hover:scale-[1.02]"
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      {/* Cover / Collage Preview Area */}
      <div className="relative aspect-[4/3] w-full bg-[var(--bg-tertiary)] overflow-hidden border-b border-default">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-brand" />
          </div>
        ) : isError || total === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>
            No preview available
          </div>
        ) : total >= 4 ? (
          /* 2x2 Collage */
          <div className="grid grid-cols-2 grid-rows-2 h-full w-full gap-[2px] p-[2px]">
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
          /* Single large cover image */
          <img
            src={getThumbnailUrl(items[0].id)}
            alt={items[0].filename}
            loading="lazy"
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        )}
      </div>

      {/* Collection Details Area */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <h3 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>{name}</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0" style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-secondary)" }}>
              {isLoading ? "..." : `${total} photo${total === 1 ? "" : "s"}`}
            </span>
          </div>
          <p className="text-xs line-clamp-2" style={{ color: "var(--text-tertiary)" }}>{description}</p>
        </div>
      </div>
    </Link>
  );
}

export default function CollectionsPage() {
  return (
    <>
      <PageHeader title="Smart Collections" description="AI-generated automatic categories curated from image contents" />

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {staticCollections.map((col) => (
          <CollectionCard
            key={col.slug}
            slug={col.slug}
            name={col.name}
            description={col.description}
          />
        ))}
      </div>

      <div className="mt-8 p-5 rounded-xl border border-default flex gap-3 items-start" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <FolderOpen className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Semantic Grouping</h4>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            These albums are populated dynamically using CLIP embeddings. There is no manual categorization required.
          </p>
        </div>
      </div>
    </>
  );
}
