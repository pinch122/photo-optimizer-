"use client";

import { useState, useEffect } from "react";
import PageHeader from "@/components/layout/PageHeader";
import Link from "next/link";
import {
  FolderOpen,
  Loader2,
  Star,
  Plus,
  Search,
  Pencil,
  Trash2,
  X,
  Tag,
  AlertTriangle,
  Brain,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl } from "@/lib/api";
import { SearchResult } from "@/lib/types";

export interface SmartCollection {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  isCustom?: boolean;
}

const DEFAULT_COLLECTIONS: SmartCollection[] = [
  { id: "beach",    name: "Beaches",    description: "Sandy shores and ocean horizons",        keywords: ["beach", "ocean", "sea", "sand"] },
  { id: "dog",      name: "Dogs",       description: "Your favorite furry companions",          keywords: ["dog", "puppy", "canine", "pet"] },
  { id: "food",     name: "Food",       description: "Gastronomic adventures and dishes",       keywords: ["food", "dish", "meal", "cooking", "restaurant"] },
  { id: "receipt",  name: "Receipts",   description: "Scanned documents and bills",             keywords: ["receipt", "bill", "invoice"] },
  { id: "college",  name: "College",    description: "Campus days and class memories",          keywords: ["college", "campus", "university", "classroom"] },
  { id: "car",      name: "Vehicles",   description: "Cars, drives, and trips",                 keywords: ["car", "vehicle", "automobile", "drive"] },
  { id: "mountain", name: "Mountains",  description: "High peaks and forest trails",            keywords: ["mountain", "hiking", "trail", "peak"] },
  { id: "document", name: "Documents",  description: "Invoices, notes, and records",            keywords: ["document", "text", "paper", "notes"] },
];

const PINNED_STORAGE_KEY  = "photomind_pinned_collections";
const CUSTOM_STORAGE_KEY  = "photomind_custom_collections";
// How many Similar Photos to show before collapsing
const SIMILAR_PREVIEW_COUNT = 4;

interface CollectionCardProps {
  collection: SmartCollection;
  isPinned: boolean;
  onTogglePin: (id: string) => void;
  onEdit: (col: SmartCollection) => void;
  onItemCountChange: (id: string, confirmed: number, similar: number) => void;
}

function CollectionCard({
  collection,
  isPinned,
  onTogglePin,
  onEdit,
  onItemCountChange,
}: CollectionCardProps) {
  const searchQuery = collection.keywords.length > 0
    ? collection.keywords.join(" ")
    : collection.name;

  const [showAllSimilar, setShowAllSimilar] = useState(false);

  // Use the existing search API — it already returns excellent_matches + similar_photos
  const { data, isLoading, isError } = useQuery({
    queryKey: ["collection-preview", collection.id, searchQuery],
    queryFn: () => searchMedia(searchQuery, 24, 0),
    staleTime: 30000,
  });

  // ── Derived: use excellent_matches as "Confirmed", similar_photos as "Similar"
  // Fall back to items[] for backward compat with any cached responses
  const confirmed: SearchResult[] = data?.excellent_matches ?? data?.items ?? [];
  const similar: SearchResult[]   = data?.similar_photos   ?? [];

  // Deduplicate: remove from similar anything already in confirmed
  const confirmedIds = new Set(confirmed.map((x) => x.id));
  const uniqueSimilar = similar.filter((x) => !confirmedIds.has(x.id));

  const confirmedCount = confirmed.length;
  const similarCount   = uniqueSimilar.length;
  const totalCount     = confirmedCount + similarCount;

  useEffect(() => {
    if (!isLoading) {
      onItemCountChange(collection.id, confirmedCount, similarCount);
    }
  }, [confirmedCount, similarCount, isLoading, collection.id]);

  // Hide collections with zero confirmed AND zero similar once we have data
  if (!isLoading && (isError || totalCount === 0)) {
    return null;
  }

  // Cover images: prefer confirmed, pad with similar if needed
  const coverImages = [
    ...confirmed.slice(0, 4),
    ...uniqueSimilar.slice(0, Math.max(0, 4 - confirmed.length)),
  ].slice(0, 4);

  // Similar photos visible slice
  const visibleSimilar = showAllSimilar
    ? uniqueSimilar
    : uniqueSimilar.slice(0, SIMILAR_PREVIEW_COUNT);

  return (
    <div
      className={`group relative flex flex-col rounded-2xl border transition-all duration-200 overflow-hidden ${
        isPinned
          ? "border-brand/40 shadow-lg shadow-brand/5"
          : "border-default hover:border-[var(--border-subtle)]"
      }`}
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      {/* ── Cover / Collage Preview ───────────────────────────────── */}
      <Link
        href={`/search?q=${encodeURIComponent(searchQuery)}`}
        className="block relative aspect-[4/3] w-full bg-[var(--bg-tertiary)] overflow-hidden border-b border-default"
      >
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-brand" />
          </div>
        ) : coverImages.length >= 4 ? (
          <div className="grid grid-cols-2 grid-rows-2 h-full w-full gap-[2px] p-[2px]">
            {coverImages.slice(0, 4).map((item) => (
              <div key={item.id} className="relative overflow-hidden w-full h-full bg-[var(--bg-secondary)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getThumbnailUrl(item.id)}
                  alt={item.filename}
                  loading="lazy"
                  className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              </div>
            ))}
          </div>
        ) : coverImages.length > 0 ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={getThumbnailUrl(coverImages[0].id)}
            alt={coverImages[0].filename}
            loading="lazy"
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-xs" style={{ color: "var(--text-tertiary)" }}>
            No preview available
          </div>
        )}
      </Link>

      {/* ── Top Action Overlays ───────────────────────────────────── */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5">
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onTogglePin(collection.id); }}
          className={`p-1.5 rounded-lg backdrop-blur-md transition-all ${
            isPinned
              ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-sm"
              : "bg-black/40 text-zinc-400 hover:text-white hover:bg-black/60 border border-white/10"
          }`}
          title={isPinned ? "Unpin from Favorites" : "Pin to Favorites"}
        >
          <Star className={`w-3.5 h-3.5 ${isPinned ? "fill-amber-400 text-amber-400" : ""}`} />
        </button>

        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onEdit(collection); }}
          className="p-1.5 rounded-lg bg-black/40 text-zinc-400 hover:text-white hover:bg-black/60 border border-white/10 backdrop-blur-md transition-all"
          title="Edit Collection"
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Collection Header ─────────────────────────────────────── */}
      <div className="p-4 flex-1 flex flex-col space-y-3">
        <div>
          <div className="flex items-start justify-between gap-2 mb-1">
            <Link href={`/search?q=${encodeURIComponent(searchQuery)}`}>
              <h3 className="text-sm font-bold truncate hover:text-brand transition-colors" style={{ color: "var(--text-primary)" }}>
                {collection.name}
              </h3>
            </Link>

            {/* Two-tier count badge */}
            {isLoading ? (
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold flex-shrink-0 bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] border border-default">
                ...
              </span>
            ) : (
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold flex-shrink-0 bg-brand/10 text-brand border border-brand/20 whitespace-nowrap">
                {confirmedCount > 0 && similarCount > 0
                  ? `${confirmedCount} Confirmed • ${similarCount} Similar`
                  : confirmedCount > 0
                  ? `${confirmedCount} Confirmed`
                  : `${similarCount} Similar`}
              </span>
            )}
          </div>

          {collection.description && (
            <p className="text-xs line-clamp-2 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {collection.description}
            </p>
          )}
        </div>

        {/* Keywords Chips */}
        {collection.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-2 border-t border-default">
            {collection.keywords.slice(0, 4).map((kw) => (
              <span key={kw} className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] border border-default">
                #{kw}
              </span>
            ))}
            {collection.keywords.length > 4 && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]">
                +{collection.keywords.length - 4}
              </span>
            )}
          </div>
        )}

        {/* ── ⭐ Confirmed Photos ─────────────────────────────────── */}
        {!isLoading && confirmed.length > 0 && (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                ⭐ Confirmed
              </span>
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-brand/10 text-brand border border-brand/20 font-bold">
                {confirmed.length}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {confirmed.slice(0, 8).map((item) => (
                <Link key={item.id} href={`/media/${item.id}`} className="relative aspect-square overflow-hidden rounded-md bg-[var(--bg-tertiary)] block">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    loading="lazy"
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-200"
                  />
                  <span className="absolute bottom-0.5 right-0.5 px-1 py-0.5 rounded text-[7px] font-bold bg-brand text-white leading-none">
                    ✓
                  </span>
                </Link>
              ))}
            </div>
            {confirmed.length > 8 && (
              <Link
                href={`/search?q=${encodeURIComponent(searchQuery)}`}
                className="text-[10px] font-semibold text-brand hover:underline"
              >
                +{confirmed.length - 8} more confirmed →
              </Link>
            )}
          </div>
        )}

        {/* ── 🔍 Similar Photos ──────────────────────────────────── */}
        {!isLoading && uniqueSimilar.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-default">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                  🔍 Similar
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-default font-bold">
                  {uniqueSimilar.length}
                </span>
              </div>
              {uniqueSimilar.length > SIMILAR_PREVIEW_COUNT && (
                <button
                  onClick={(e) => { e.preventDefault(); setShowAllSimilar((v) => !v); }}
                  className="flex items-center gap-0.5 text-[9px] font-semibold hover:text-brand transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {showAllSimilar ? (
                    <><ChevronUp className="w-3 h-3" /> Less</>
                  ) : (
                    <><ChevronDown className="w-3 h-3" /> +{uniqueSimilar.length - SIMILAR_PREVIEW_COUNT} more</>
                  )}
                </button>
              )}
            </div>
            <div className="grid grid-cols-4 gap-1">
              {visibleSimilar.map((item) => (
                <Link key={item.id} href={`/media/${item.id}`} className="relative aspect-square overflow-hidden rounded-md bg-[var(--bg-tertiary)] block">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getThumbnailUrl(item.id)}
                    alt={item.filename}
                    loading="lazy"
                    className="w-full h-full object-cover opacity-80 hover:opacity-100 hover:scale-105 transition-all duration-200"
                  />
                  <span className="absolute bottom-0.5 right-0.5 px-1 py-0.5 rounded text-[7px] font-bold bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-default leading-none">
                    ~
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function CollectionsPage() {
  const queryClient = useQueryClient();
  const [pinnedIds, setPinnedIds]             = useState<Set<string>>(new Set());
  const [customCollections, setCustomCollections] = useState<SmartCollection[]>([]);
  const [searchFilter, setSearchFilter]       = useState("");
  // countsMap: id → { confirmed, similar }
  const [countsMap, setCountsMap]             = useState<Record<string, { confirmed: number; similar: number }>>({});

  // Modal State
  const [activeModal, setActiveModal]         = useState<"create" | "edit" | "delete" | null>(null);
  const [targetCollection, setTargetCollection] = useState<SmartCollection | null>(null);

  // Form State
  const [formName, setFormName]               = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formKeywords, setFormKeywords]       = useState<string[]>([]);
  const [keywordInput, setKeywordInput]       = useState("");

  useEffect(() => {
    try {
      const storedPinned = localStorage.getItem(PINNED_STORAGE_KEY);
      if (storedPinned) setPinnedIds(new Set(JSON.parse(storedPinned)));
      const storedCustom = localStorage.getItem(CUSTOM_STORAGE_KEY);
      if (storedCustom) setCustomCollections(JSON.parse(storedCustom));
    } catch (e) {
      console.error("Failed to load collections state from localStorage", e);
    }
  }, []);

  const savePinnedState = (nextPinned: Set<string>) => {
    setPinnedIds(nextPinned);
    try { localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(Array.from(nextPinned))); }
    catch (e) { console.error("Failed to save pinned state", e); }
  };

  const saveCustomCollections = (nextCustom: SmartCollection[]) => {
    setCustomCollections(nextCustom);
    try { localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(nextCustom)); }
    catch (e) { console.error("Failed to save custom collections", e); }
  };

  const handleTogglePin = (id: string) => {
    const next = new Set(pinnedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    savePinnedState(next);
  };

  const handleItemCountChange = (id: string, confirmed: number, similar: number) => {
    setCountsMap((prev) => {
      const existing = prev[id];
      if (existing?.confirmed === confirmed && existing?.similar === similar) return prev;
      return { ...prev, [id]: { confirmed, similar } };
    });
  };

  // Combine default and custom collections
  const allCollectionsMap = new Map<string, SmartCollection>();
  DEFAULT_COLLECTIONS.forEach((c)    => allCollectionsMap.set(c.id, c));
  customCollections.forEach((c)      => allCollectionsMap.set(c.id, c));
  const allCollectionsList = Array.from(allCollectionsMap.values());

  const matchingCollections = allCollectionsList.filter((col) => {
    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase();
      if (
        !col.name.toLowerCase().includes(q) &&
        !col.description.toLowerCase().includes(q) &&
        !col.keywords.some((k) => k.toLowerCase().includes(q))
      ) return false;
    }
    const counts = countsMap[col.id];
    if (counts !== undefined && counts.confirmed === 0 && counts.similar === 0) return false;
    return true;
  });

  const favoriteCollections = matchingCollections.filter((c) => pinnedIds.has(c.id));
  const otherCollections    = matchingCollections.filter((c) => !pinnedIds.has(c.id));

  // Modal Handlers
  const openCreateModal = () => {
    setFormName(""); setFormDescription(""); setFormKeywords([]); setKeywordInput("");
    setTargetCollection(null);
    setActiveModal("create");
  };

  const openEditModal = (col: SmartCollection) => {
    setTargetCollection(col);
    setFormName(col.name); setFormDescription(col.description);
    setFormKeywords([...col.keywords]); setKeywordInput("");
    setActiveModal("edit");
  };

  const openDeleteModal = (col: SmartCollection) => {
    setTargetCollection(col);
    setActiveModal("delete");
  };

  const handleAddKeyword = () => {
    const trimmed = keywordInput.trim().toLowerCase();
    if (trimmed && !formKeywords.includes(trimmed)) {
      setFormKeywords([...formKeywords, trimmed]);
      setKeywordInput("");
    }
  };

  const handleRemoveKeyword = (kw: string) => {
    setFormKeywords(formKeywords.filter((k) => k !== kw));
  };

  const handleSaveCollection = () => {
    if (!formName.trim()) return;
    if (activeModal === "create") {
      const newCol: SmartCollection = {
        id: `custom-${Date.now()}`,
        name: formName.trim(),
        description: formDescription.trim(),
        keywords: formKeywords.length > 0 ? formKeywords : [formName.trim().toLowerCase()],
        isCustom: true,
      };
      saveCustomCollections([...customCollections, newCol]);
    } else if (activeModal === "edit" && targetCollection) {
      if (targetCollection.isCustom) {
        saveCustomCollections(
          customCollections.map((c) =>
            c.id === targetCollection.id
              ? { ...c, name: formName.trim(), description: formDescription.trim(), keywords: formKeywords }
              : c
          )
        );
      } else {
        const override: SmartCollection = {
          ...targetCollection,
          name: formName.trim(),
          description: formDescription.trim(),
          keywords: formKeywords,
        };
        const idx = customCollections.findIndex((c) => c.id === targetCollection.id);
        if (idx >= 0) {
          const next = [...customCollections];
          next[idx] = override;
          saveCustomCollections(next);
        } else {
          saveCustomCollections([...customCollections, override]);
        }
      }
    }
    queryClient.invalidateQueries({ queryKey: ["collection-preview"] });
    setActiveModal(null);
  };

  const handleDeleteCollection = () => {
    if (!targetCollection) return;
    saveCustomCollections(customCollections.filter((c) => c.id !== targetCollection.id));
    if (pinnedIds.has(targetCollection.id)) {
      const next = new Set(pinnedIds);
      next.delete(targetCollection.id);
      savePinnedState(next);
    }
    queryClient.invalidateQueries({ queryKey: ["collection-preview"] });
    setActiveModal(null);
    setTargetCollection(null);
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Top Banner */}
      <div
        className="rounded-2xl border border-default p-6 sm:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-6"
        style={{
          backgroundColor: "var(--bg-secondary)",
          backgroundImage: "radial-gradient(circle at 100% 0%, var(--brand-glow) 0%, transparent 60%)",
        }}
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2.5" style={{ color: "var(--text-primary)" }}>
            <Sparkles className="w-7 h-7 text-brand" /> Smart Collections
          </h1>
          <p className="text-sm mt-1.5 max-w-xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            PhotoMind AI automatically populates your collections using natural language understanding. Confirmed photos have strong metadata evidence; Similar photos are semantically close.
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="px-4 py-2.5 rounded-xl text-xs font-extrabold text-white bg-brand hover:bg-brand-hover shadow-lg shadow-brand/20 transition-all flex items-center gap-2 flex-shrink-0"
        >
          <Plus className="w-4 h-4" /> New Smart Collection
        </button>
      </div>

      {/* Search Filter */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-tertiary)" }} />
        <input
          type="text"
          placeholder="Search collection names or keywords..."
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 rounded-xl text-xs font-medium border border-default bg-[var(--bg-secondary)] focus:outline-none focus:border-brand transition-colors"
          style={{ color: "var(--text-primary)" }}
        />
        {searchFilter && (
          <button
            onClick={() => setSearchFilter("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* ⭐ Favorites */}
      {favoriteCollections.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-default">
            <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-amber-400">
              Favorites ({favoriteCollections.length})
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {favoriteCollections.map((col) => (
              <CollectionCard
                key={col.id}
                collection={col}
                isPinned={true}
                onTogglePin={handleTogglePin}
                onEdit={openEditModal}
                onItemCountChange={handleItemCountChange}
              />
            ))}
          </div>
        </section>
      )}

      {/* AI Collections */}
      {otherCollections.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-default">
            <Brain className="w-4 h-4 text-brand" />
            <h2 className="text-sm font-extrabold uppercase tracking-wider" style={{ color: "var(--text-primary)" }}>
              {favoriteCollections.length > 0 ? "Other Collections" : "AI Collections"} ({otherCollections.length})
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {otherCollections.map((col) => (
              <CollectionCard
                key={col.id}
                collection={col}
                isPinned={false}
                onTogglePin={handleTogglePin}
                onEdit={openEditModal}
                onItemCountChange={handleItemCountChange}
              />
            ))}
          </div>
        </section>
      )}

      {/* Empty State */}
      {favoriteCollections.length === 0 && otherCollections.length === 0 && (
        <div className="p-16 rounded-2xl border border-default text-center flex flex-col items-center justify-center min-h-[40vh]" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <div className="w-16 h-16 rounded-2xl bg-brand/10 flex items-center justify-center mb-4 border border-brand/20">
            <FolderOpen className="w-8 h-8 text-brand" />
          </div>
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
            {searchFilter ? "No collections match your search" : "No Collections Yet"}
          </h2>
          <p className="text-xs mt-1.5 max-w-sm leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
            {searchFilter
              ? "Try adjusting your search query or clear the filter."
              : "Create your first Smart Collection and PhotoMind AI will organize matching photos automatically."}
          </p>
          {!searchFilter && (
            <button
              onClick={openCreateModal}
              className="mt-6 px-4 py-2.5 rounded-xl text-xs font-extrabold text-white bg-brand hover:bg-brand-hover transition-all flex items-center gap-2 shadow-lg shadow-brand/20"
            >
              <Plus className="w-4 h-4" /> Create Collection
            </button>
          )}
        </div>
      )}

      {/* Info Box */}
      <div className="p-5 rounded-2xl border border-default flex gap-3 items-start" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <Brain className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Two-Tier Semantic Organization</h4>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
            <strong className="text-[var(--text-secondary)]">⭐ Confirmed</strong> — photos with strong metadata evidence (captions, objects, keywords).{" "}
            <strong className="text-[var(--text-secondary)]">🔍 Similar</strong> — visually or semantically close photos that lack explicit metadata.
          </p>
        </div>
      </div>

      {/* ── Modals ────────────────────────────────────────────────── */}

      {/* Create / Edit */}
      {(activeModal === "create" || activeModal === "edit") && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl border border-default bg-[var(--bg-secondary)] shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-default pb-3">
              <h3 className="text-base font-extrabold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                <Sparkles className="w-4 h-4 text-brand" />
                {activeModal === "create" ? "New Smart Collection" : "Edit Smart Collection"}
              </h3>
              <button onClick={() => setActiveModal(null)} className="p-1 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>Collection Name *</label>
              <input
                type="text"
                placeholder="e.g. Travel, Boxing, Work"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl text-xs border border-default bg-[var(--bg-primary)] focus:outline-none focus:border-brand"
                style={{ color: "var(--text-primary)" }}
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>Description (Optional)</label>
              <input
                type="text"
                placeholder="e.g. Vacation trips, campus memories..."
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl text-xs border border-default bg-[var(--bg-primary)] focus:outline-none focus:border-brand"
                style={{ color: "var(--text-primary)" }}
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold flex items-center justify-between" style={{ color: "var(--text-primary)" }}>
                <span>Keywords (AI Matching)</span>
                <span className="text-[10px] text-brand font-normal">Press Enter or Add</span>
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. beach, mountain, hotel..."
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddKeyword(); } }}
                  className="flex-1 px-3.5 py-2 rounded-xl text-xs border border-default bg-[var(--bg-primary)] focus:outline-none focus:border-brand"
                  style={{ color: "var(--text-primary)" }}
                />
                <button
                  type="button"
                  onClick={handleAddKeyword}
                  className="px-3 py-2 rounded-xl text-xs font-bold bg-brand/10 text-brand border border-brand/30 hover:bg-brand/20 transition-colors"
                >
                  Add
                </button>
              </div>

              {formKeywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-2">
                  {formKeywords.map((kw) => (
                    <span
                      key={kw}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-brand/10 text-brand border border-brand/20"
                    >
                      <Tag className="w-3 h-3" />
                      {kw}
                      <button onClick={() => handleRemoveKeyword(kw)} className="hover:text-rose-400 transition-colors">
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-default">
              {activeModal === "edit" ? (
                <button
                  onClick={() => openDeleteModal(targetCollection!)}
                  className="px-3 py-2 rounded-xl text-xs font-bold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 transition-colors flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete Collection
                </button>
              ) : <div />}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveCollection}
                  disabled={!formName.trim()}
                  className="px-4 py-2 rounded-xl text-xs font-extrabold text-white bg-brand hover:bg-brand-hover transition-colors disabled:opacity-50"
                >
                  Save Collection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete */}
      {activeModal === "delete" && targetCollection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl border border-default bg-[var(--bg-secondary)] shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-extrabold" style={{ color: "var(--text-primary)" }}>Delete Collection?</h3>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Photos will NOT be deleted.</p>
              </div>
            </div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Are you sure you want to delete <strong className="text-white">{targetCollection.name}</strong>? Only the collection rule will be removed. All photos remain safe in your library.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteCollection}
                className="px-4 py-2 rounded-xl text-xs font-extrabold text-white bg-rose-500 hover:bg-rose-600 transition-colors flex items-center gap-2"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete Collection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
