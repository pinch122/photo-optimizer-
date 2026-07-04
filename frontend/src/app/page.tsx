"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listMedia } from "@/lib/api";
import { Search, Upload, Brain, Loader2 } from "lucide-react";
import Link from "next/link";

const exampleSearches = [
  "Find my Goa trip",
  "Find beach photos",
  "Show my dog",
  "Find receipts",
  "College memories",
];

export default function LandingPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  // Check if library is empty
  const { data: mediaData, isLoading } = useQuery({
    queryKey: ["check-empty-library"],
    queryFn: () => listMedia(1, 0),
  });

  const totalPhotos = mediaData?.total ?? 0;

  // Automatically redirect if empty
  useEffect(() => {
    if (!isLoading && mediaData && totalPhotos === 0) {
      router.push("/upload");
    }
  }, [mediaData, totalPhotos, isLoading, router]);

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] text-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand mb-4" />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Initializing PhotoMind AI...
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[75vh] px-4 text-center">
      {/* Brand logo & title */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-brand/20">
          <Brain className="w-7 h-7 text-brand" />
        </div>
        <h1
          className="text-4xl sm:text-5xl font-extrabold tracking-tight"
          style={{ color: "var(--text-primary)" }}
        >
          PhotoMind AI
        </h1>
      </div>

      {/* Tagline */}
      <p
        className="text-lg sm:text-xl mb-8 max-w-lg"
        style={{ color: "var(--text-secondary)" }}
      >
        Find any memory instantly using AI.
      </p>

      {/* Oversized Search Bar */}
      <form onSubmit={handleSearch} className="relative w-full max-w-2xl mb-6">
        <div className="relative">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5"
            style={{ color: "var(--text-tertiary)" }}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your photo library..."
            className="w-full h-14 pl-12 pr-24 rounded-xl border border-default text-base transition-all duration-200 focus:border-brand focus:shadow-glow outline-none"
            style={{
              backgroundColor: "var(--bg-secondary)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 h-9 px-4 rounded-lg text-xs font-semibold text-white bg-brand hover:bg-brand-hover transition-colors"
          >
            Search
          </button>
        </div>
      </form>

      {/* Example Prompts */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-10 max-w-xl">
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          Try:
        </span>
        {exampleSearches.map((prompt) => (
          <button
            key={prompt}
            onClick={() => {
              // Convert natural phrases into simple query strings if needed, or search literally
              const q = prompt.replace(/Find my |Find |Show my |Show /g, "");
              router.push(`/search?q=${encodeURIComponent(q)}`);
            }}
            className="px-3.5 py-1.5 rounded-full text-xs font-medium border border-default transition-colors duration-150 hover:border-brand/50 hover:text-brand"
            style={{
              backgroundColor: "var(--bg-secondary)",
              color: "var(--text-secondary)",
            }}
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Upload Images Button */}
      <Link
        href="/upload"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white bg-brand hover:bg-brand-hover transition-all duration-200 hover:scale-[1.02] shadow-sm hover:shadow-md"
      >
        <Upload className="w-4 h-4" />
        Upload Images
      </Link>
    </div>
  );
}
