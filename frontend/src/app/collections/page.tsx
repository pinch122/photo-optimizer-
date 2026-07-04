"use client";

import PageHeader from "@/components/layout/PageHeader";
import Link from "next/link";
import { FolderOpen } from "lucide-react";

const staticCollections = [
  { slug: "beach", name: "Beaches", emoji: "🏖️", count: 24, description: "Sandy shores and ocean horizons" },
  { slug: "dog", name: "Dogs", emoji: "🐕", count: 18, description: "Your favorite furry companions" },
  { slug: "food", name: "Food", emoji: "🍕", count: 31, description: "Gastronomic adventures and dishes" },
  { slug: "receipt", name: "Receipts", emoji: "🧾", count: 12, description: "Scanned documents and bills" },
  { slug: "college", name: "College", emoji: "🎓", count: 0, description: "Campus days and class memories" },
  { slug: "car", name: "Vehicles", emoji: "🚗", count: 7, description: "Cars, drives, and trips" },
  { slug: "mountain", name: "Mountains", emoji: "🏔️", count: 0, description: "High peaks and forest trails" },
  { slug: "document", name: "Documents", emoji: "📄", count: 4, description: "Invoices, notes, and records" },
];

export default function CollectionsPage() {
  return (
    <>
      <PageHeader title="Smart Collections" description="AI-generated automatic categories curated from image contents" />

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {staticCollections.map((col) => (
          <Link
            key={col.slug}
            href={`/search?q=${col.slug}`}
            className="group rounded-xl border border-default p-5 transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
            style={{ backgroundColor: "var(--bg-secondary)" }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-3xl transition-transform duration-200 group-hover:scale-110">{col.emoji}</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-secondary)" }}>
                {col.count} items
              </span>
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{col.name}</h3>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{col.description}</p>
          </Link>
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
