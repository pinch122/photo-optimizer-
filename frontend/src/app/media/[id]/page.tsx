"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMediaDetail, getThumbnailUrl, getOriginalUrl, reprocessMedia, getSimilarMedia } from "@/lib/api";
import { formatFileSize, formatDate } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatusBadge from "@/components/shared/StatusBadge";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft, Download, RotateCw, Camera, MapPin, Calendar,
  Ruler, Aperture, Zap, FileImage, Brain, Loader2,
} from "lucide-react";

export default function MediaDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const queryClient = useQueryClient();
  const [showSimilar, setShowSimilar] = useState(false);

  const { data: asset, isLoading, error } = useQuery({
    queryKey: ["media", id],
    queryFn: () => getMediaDetail(id),
  });

  const { data: similarImages, isLoading: isSimilarLoading } = useQuery({
    queryKey: ["similar-media", id],
    queryFn: () => getSimilarMedia(id, 20),
    enabled: showSimilar,
  });

  const reprocessMut = useMutation({
    mutationFn: () => reprocessMedia(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media", id] }),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="w-32 h-6 rounded skeleton" />
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 aspect-[4/3] rounded-xl skeleton" />
          <div className="lg:col-span-2 space-y-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-4 rounded skeleton" style={{ width: `${60 + Math.random() * 40}%` }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !asset) {
    return (
      <div className="text-center py-16">
        <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>Photo not found</p>
        <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>This photo doesn't exist or was deleted.</p>
        <Link href="/gallery" className="inline-flex items-center gap-2 mt-4 text-sm font-medium text-brand hover:text-brand-hover transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Gallery
        </Link>
      </div>
    );
  }

  const meta = asset.photo_metadata;
  const ai = asset.ai_analysis;

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Link href="/gallery" className="inline-flex items-center gap-2 text-sm font-medium transition-colors hover:text-brand" style={{ color: "var(--text-secondary)" }}>
          <ArrowLeft className="w-4 h-4" /> Back to Gallery
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSimilar(!showSimilar)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors ${
              showSimilar
                ? "border-brand text-brand bg-brand/10 hover:bg-brand/20"
                : "border-default hover:bg-[var(--bg-tertiary)]"
            }`}
            style={{ color: showSimilar ? undefined : "var(--text-secondary)" }}
          >
            <Brain className="w-3.5 h-3.5 text-purple-400" />
            Find Similar
          </button>
          <button
            onClick={() => reprocessMut.mutate()}
            disabled={reprocessMut.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-default text-xs font-medium transition-colors hover:bg-[var(--bg-tertiary)] disabled:opacity-50"
            style={{ color: "var(--text-secondary)" }}
          >
            {reprocessMut.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw className="w-3.5 h-3.5" />}
            Reprocess
          </button>
          <a
            href={getOriginalUrl(id)}
            download
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white bg-brand hover:bg-brand-hover transition-colors"
          >
            <Download className="w-3.5 h-3.5" /> Download
          </a>
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Image */}
        <div className="lg:col-span-3">
          <div
            className="relative rounded-xl overflow-hidden border border-default"
            style={{ backgroundColor: "var(--bg-tertiary)" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getOriginalUrl(id)}
              alt={asset.filename}
              className="w-full h-auto object-contain max-h-[70vh]"
            />
          </div>
        </div>

        {/* Metadata Sidebar */}
        <div className="lg:col-span-2 space-y-6">
          {/* AI Memory Record */}
          <AIMemoryRecord ai={ai} />

          {/* Image Quality (kept separate) */}
          <MetadataSection title="Image Quality" icon={FileImage}>
            <div className="flex flex-wrap gap-1.5">
              {(() => {
                const quality = (ai?.processing_status === "COMPLETED" ? null : ai?.keywords) || {};
                const brightness = quality.brightness ?? 0.5;
                const darkness = quality.darkness ?? 0.5;
                const blur_score = quality.blur_score ?? 0;
                const sharpness = quality.sharpness ?? 0;

                let sharpnessStars = "★★☆☆☆";
                let sharpnessLabel = "Soft";
                if (sharpness >= 45) { sharpnessStars = "★★★★★"; sharpnessLabel = "Sharp"; }
                else if (sharpness >= 30) { sharpnessStars = "★★★★☆"; sharpnessLabel = "Sharp"; }
                else if (sharpness >= 15) { sharpnessStars = "★★★☆☆"; sharpnessLabel = "Moderate"; }

                const badges = [
                  <span key="sharp" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {sharpnessStars} {sharpnessLabel}
                  </span>
                ];
                if (brightness > 0.65) badges.push(
                  <span key="bright" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">☀ Bright</span>
                );
                if (darkness > 0.65) badges.push(
                  <span key="dark" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-500/10 text-zinc-400 border border-zinc-500/20">🌑 Dark</span>
                );
                if (blur_score > 35) badges.push(
                  <span key="blurry" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20">🌫 Blurry</span>
                );
                if (meta && meta.width * meta.height >= 2073600) badges.push(
                  <span key="hd" className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">HD High Resolution</span>
                );
                return badges;
              })()}
            </div>
            <MetadataRow label="Duplicate Status" value={asset.p_hash ? "Ready for detection" : "No perceptual hash"} />
          </MetadataSection>

          {/* File Info */}
          <MetadataSection title="File Information" icon={FileImage}>
            <MetadataRow label="Name" value={asset.filename} />
            <MetadataRow label="Mime Type" value={asset.mime_type} mono />
            <MetadataRow label="Media Type" value={asset.media_type} />
            <MetadataRow label="Size" value={formatFileSize(asset.file_size)} />
            <MetadataRow label="Status" value={<StatusBadge status={asset.status} />} />
            <MetadataRow label="Uploaded" value={formatDate(asset.created_at)} />
            {asset.taken_at && <MetadataRow label="Taken" value={formatDate(asset.taken_at)} />}
          </MetadataSection>

          {/* Camera Details */}
          {meta && (
            <MetadataSection title="Camera Details" icon={Camera}>
              <MetadataRow label="Resolution" value={`${meta.width} × ${meta.height}`} />
              {meta.camera_make && <MetadataRow label="Make" value={meta.camera_make} />}
              {meta.camera_model && <MetadataRow label="Model" value={meta.camera_model} />}
              {meta.exposure_time && <MetadataRow label="Exposure" value={meta.exposure_time} />}
              {meta.f_number && <MetadataRow label="Aperture" value={`f/${meta.f_number}`} />}
              {meta.iso_speed && <MetadataRow label="ISO" value={meta.iso_speed.toString()} />}
            </MetadataSection>
          )}
        </div>
      </div>

      {/* Similar Images Section */}
      {showSimilar && (
        <div className="mt-8 p-6 rounded-xl border border-default animate-fadeIn" style={{ backgroundColor: "var(--bg-secondary)" }}>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-400" />
              <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                AI-Powered Similar Images
              </h3>
            </div>
            <button
              onClick={() => setShowSimilar(false)}
              className="text-xs font-semibold text-brand hover:underline"
            >
              Close
            </button>
          </div>

          {isSimilarLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 animate-pulse">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="aspect-square rounded-lg skeleton" />
              ))}
            </div>
          ) : !similarImages || similarImages.length === 0 ? (
            <p className="text-sm py-4 text-center" style={{ color: "var(--text-tertiary)" }}>
              No similar images found with similarity ≥ 80%.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {similarImages.map((sim) => {
                const pct = Math.round(sim.similarity_percentage);
                let badgeLabel = "";
                let badgeClass = "";
                if (pct >= 98) {
                  badgeLabel = "⭐ Near Duplicate";
                  badgeClass = "bg-purple-500/20 text-purple-400 border border-purple-500/30";
                } else if (pct >= 95) {
                  badgeLabel = "🟣 Extremely Similar";
                  badgeClass = "bg-purple-600/20 text-purple-400 border border-purple-600/30";
                } else if (pct >= 90) {
                  badgeLabel = "🔵 Very Similar";
                  badgeClass = "bg-blue-500/20 text-blue-400 border border-blue-500/30";
                } else if (pct >= 80) {
                  badgeLabel = "⚪ Similar";
                  badgeClass = "bg-zinc-500/20 text-zinc-400 border border-zinc-500/30";
                }

                return (
                  <Link
                    key={sim.id}
                    href={`/media/${sim.id}`}
                    className="group relative aspect-square rounded-lg overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={sim.thumbnail_url}
                      alt={sim.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    
                    {/* Badge Overlay */}
                    {badgeLabel && (
                      <span className={`absolute top-2 left-2 z-10 px-1.5 py-0.5 rounded text-[8px] font-bold shadow-sm ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                    )}

                    {/* Hover title */}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/45 transition-all duration-200 flex items-end pointer-events-none">
                      <div className="w-full p-2 translate-y-full group-hover:translate-y-0 transition-transform duration-200 bg-gradient-to-t from-black/80 to-transparent">
                        <p className="text-[10px] font-medium text-white truncate">{sim.filename}</p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Processing Timeline */}
      <div className="mt-8 p-6 rounded-xl border border-default" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
          Processing Timeline
        </h3>
        <div className="flex items-center gap-2 overflow-x-auto">
          {["Uploaded", "Metadata Extracted", "Thumbnail Generated", "Embedding Generated", "Ready"].map((step, i) => {
            const stepStatuses: Record<string, number> = {
              UPLOADED: 0, PROCESSING: 2, READY: 4, FAILED: -1,
            };
            const currentStep = stepStatuses[asset.status] ?? -1;
            const isComplete = i <= currentStep;
            const isCurrent = i === currentStep;

            return (
              <div key={step} className="flex items-center gap-2">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-3 h-3 rounded-full border-2 transition-all duration-300 ${
                      isComplete
                        ? "bg-[var(--success)] border-[var(--success)]"
                        : asset.status === "FAILED" && i === 0
                        ? "bg-[var(--error)] border-[var(--error)]"
                        : "border-[var(--border-subtle)]"
                    } ${isCurrent ? "ring-4 ring-[var(--success)]/20" : ""}`}
                  />
                  <span className="text-[10px] mt-1.5 whitespace-nowrap" style={{ color: isComplete ? "var(--text-secondary)" : "var(--text-tertiary)" }}>
                    {step}
                  </span>
                </div>
                {i < 4 && (
                  <div
                    className="w-8 sm:w-12 h-0.5 rounded-full mt-[-12px]"
                    style={{ backgroundColor: isComplete ? "var(--success)" : "var(--bg-tertiary)" }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function MetadataSection({ title, icon: Icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-default p-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4" style={{ color: "var(--text-tertiary)" }} />
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function MetadataRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span style={{ color: "var(--text-tertiary)" }}>{label}</span>
      <span className={mono ? "font-mono text-xs" : ""} style={{ color: "var(--text-secondary)" }}>
        {value}
      </span>
    </div>
  );
}

// ─── AI Memory Record Component ───────────────────────────────────────────────

function AIMemoryRecord({ ai }: { ai: any }) {
  const status = ai?.processing_status;

  // ── Not yet analysed ──────────────────────────────────────────────────────
  if (!ai || (!status && !ai.caption)) {
    return (
      <div className="rounded-lg border border-default p-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Memory Record</h3>
        </div>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>No AI analysis data available for this image.</p>
      </div>
    );
  }

  // ── Processing states ─────────────────────────────────────────────────────
  if (status === "PENDING" || status === "PROCESSING") {
    return (
      <div className="rounded-lg border border-default p-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Memory Record</h3>
        </div>
        <div className="flex items-center gap-2 py-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>AI analysis in progress…</span>
        </div>
      </div>
    );
  }

  // ── Skipped / not configured ──────────────────────────────────────────────
  if (status === "SKIPPED_NO_PROVIDER") {
    return (
      <div className="rounded-lg border border-default p-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-4 h-4 text-zinc-500" />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Memory Record</h3>
        </div>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          AI analysis not configured. Set <code className="font-mono text-purple-400">GEMINI_API_KEY</code> in your environment to enable.
        </p>
      </div>
    );
  }

  // ── Failed ────────────────────────────────────────────────────────────────
  if (status === "FAILED") {
    return (
      <div className="rounded-lg border border-default p-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-4 h-4 text-red-400" />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Memory Record</h3>
          <span className="ml-auto px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500/15 text-red-400 border border-red-500/20">FAILED</span>
        </div>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          Analysis failed. Use Reprocess to retry.
        </p>
      </div>
    );
  }

  // ── Completed — full Memory Record ────────────────────────────────────────
  const tags: string[] = ai.keywords?.tags ?? [];
  const objects: string[] = ai.objects ?? [];
  const activities: string[] = ai.activities ?? [];
  const colors: string[] = ai.dominant_colors ?? [];

  return (
    <div className="rounded-lg border border-default p-4 space-y-4" style={{ backgroundColor: "var(--bg-secondary)" }}>

      {/* Header */}
      <div className="flex items-center gap-2">
        <Brain className="w-4 h-4 text-purple-400" />
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Memory Record</h3>
        <span className="ml-auto px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/15 text-purple-400 border border-purple-500/20">
          COMPLETED
        </span>
      </div>

      {/* Caption */}
      {ai.caption && (
        <div>
          <p className="text-sm font-medium leading-snug" style={{ color: "var(--text-primary)" }}>
            "{ai.caption}"
          </p>
        </div>
      )}

      {/* Description (collapsible) */}
      {ai.detailed_description && (
        <details className="group">
          <summary className="text-[11px] font-semibold cursor-pointer select-none" style={{ color: "var(--text-tertiary)" }}>
            Full Description ▸
          </summary>
          <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {ai.detailed_description}
          </p>
        </details>
      )}

      {/* Scene & Context grid */}
      <div className="grid grid-cols-2 gap-1.5 text-xs">
        {ai.scene && (
          <Chip label="Scene" value={cap(ai.scene)} color="blue" />
        )}
        {ai.indoor_outdoor && (
          <Chip label={cap(ai.indoor_outdoor)} value="" color="zinc" icon={ai.indoor_outdoor === "outdoor" ? "🌿" : "🏠"} />
        )}
        {ai.weather && (
          <Chip label="Weather" value={cap(ai.weather)} color="sky" />
        )}
        {ai.season && (
          <Chip label="Season" value={cap(ai.season)} color="green" />
        )}
        {ai.mood && (
          <Chip label="Mood" value={cap(ai.mood)} color="pink" />
        )}
        {typeof ai.people_count === "number" && (
          <Chip label="People" value={ai.people_count === 0 ? "None" : String(ai.people_count)} color="amber" icon="👤" />
        )}
      </div>

      {/* Memory Tags */}
      {(ai.event_type || ai.travel_event || ai.location_guess) && (
        <div className="space-y-1 pt-1 border-t border-default">
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Memory</span>
          <div className="flex flex-wrap gap-1">
            {ai.event_type && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/15 text-violet-400 border border-violet-500/20">
                🎉 {cap(ai.event_type.replace(/_/g, " "))}
              </span>
            )}
            {ai.travel_event && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-500/15 text-teal-400 border border-teal-500/20">
                ✈ Travel
              </span>
            )}
            {ai.location_guess && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-400 border border-blue-500/20">
                📍 {ai.location_guess}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Dominant Colors */}
      {colors.length > 0 && (
        <div className="space-y-1 pt-1 border-t border-default">
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Colors</span>
          <div className="flex items-center gap-2">
            {colors.map((hex) => (
              <div key={hex} className="flex flex-col items-center gap-1">
                <div
                  className="w-6 h-6 rounded-md border border-white/10 shadow-sm"
                  style={{ backgroundColor: hex }}
                  title={hex}
                />
                <span className="text-[8px] font-mono" style={{ color: "var(--text-tertiary)" }}>{hex}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Objects & Activities */}
      {(objects.length > 0 || activities.length > 0) && (
        <div className="space-y-1 pt-1 border-t border-default">
          {objects.length > 0 && (
            <>
              <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Objects</span>
              <div className="flex flex-wrap gap-1">
                {objects.map((o) => (
                  <span key={o} className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-300 border border-zinc-700">{cap(o)}</span>
                ))}
              </div>
            </>
          )}
          {activities.length > 0 && (
            <>
              <span className="text-[10px] font-semibold uppercase tracking-wider mt-1.5 block" style={{ color: "var(--text-tertiary)" }}>Activities</span>
              <div className="flex flex-wrap gap-1">
                {activities.map((a) => (
                  <span key={a} className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-300 border border-zinc-700">{cap(a)}</span>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Keywords / Semantic Tags */}
      {tags.length > 0 && (
        <div className="space-y-1 pt-1 border-t border-default">
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Keywords</span>
          <div className="flex flex-wrap gap-1">
            {tags.map((t) => (
              <span key={t} className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{cap(t)}</span>
            ))}
          </div>
        </div>
      )}

      {/* OCR / Detected Text */}
      {ai.detected_text && (
        <details className="group pt-1 border-t border-default">
          <summary className="text-[11px] font-semibold cursor-pointer select-none" style={{ color: "var(--text-tertiary)" }}>
            Detected Text ▸
          </summary>
          <pre className="mt-1.5 text-[10px] font-mono whitespace-pre-wrap leading-relaxed p-2 rounded bg-zinc-900 border border-zinc-800" style={{ color: "var(--text-secondary)" }}>
            {ai.detected_text}
          </pre>
        </details>
      )}

      {/* Model Footer */}
      {ai.model_name && (
        <div className="pt-2 border-t border-default flex items-center justify-between">
          <span className="text-[9px] font-mono" style={{ color: "var(--text-tertiary)" }}>
            {ai.model_name}
          </span>
          {ai.processed_at && (
            <span className="text-[9px]" style={{ color: "var(--text-tertiary)" }}>
              {new Date(ai.processed_at).toLocaleDateString()}
            </span>
          )}
          {typeof ai.ai_confidence === "number" && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">
              {Math.round(ai.ai_confidence * 100)}% conf
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Tiny helpers ──────────────────────────────────────────────────────────────

function cap(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

type ChipColor = "blue" | "sky" | "green" | "pink" | "amber" | "zinc";
const CHIP_COLORS: Record<ChipColor, string> = {
  blue:  "bg-blue-500/10 text-blue-400 border-blue-500/20",
  sky:   "bg-sky-500/10 text-sky-400 border-sky-500/20",
  green: "bg-green-500/10 text-green-400 border-green-500/20",
  pink:  "bg-pink-500/10 text-pink-400 border-pink-500/20",
  amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  zinc:  "bg-zinc-700/50 text-zinc-300 border-zinc-600/40",
};

function Chip({ label, value, color, icon }: { label: string; value: string; color: ChipColor; icon?: string }) {
  return (
    <div className={`flex items-center gap-1 px-2 py-1 rounded-md border text-[10px] font-medium ${CHIP_COLORS[color]}`}>
      {icon && <span>{icon}</span>}
      <span className="opacity-70">{label}</span>
      {value && <span className="font-semibold">{value}</span>}
    </div>
  );
}

