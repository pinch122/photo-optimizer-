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
          {/* File Info */}
          <MetadataSection title="File Information" icon={FileImage}>
            <MetadataRow label="Name" value={asset.filename} />
            <MetadataRow label="Mime Type" value={asset.mime_type} mono />
            <MetadataRow label="Media Type" value={asset.media_type} />
            <MetadataRow label="Size" value={formatFileSize(asset.file_size)} />
            <MetadataRow label="Status" value={<StatusBadge status={asset.status} />} />
            {typeof (asset as any).score === "number" && (
              <MetadataRow label="Similarity Score" value={`${Math.round((asset as any).score * 100)}%`} />
            )}
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

          {/* Location */}
          {meta && (meta.gps_latitude || meta.gps_longitude) && (
            <MetadataSection title="Location" icon={MapPin}>
              <MetadataRow label="Latitude" value={meta.gps_latitude?.toFixed(6) || "—"} mono />
              <MetadataRow label="Longitude" value={meta.gps_longitude?.toFixed(6) || "—"} mono />
            </MetadataSection>
          )}

          {/* AI Processing */}
          <MetadataSection title="AI Processing" icon={Brain}>
            <MetadataRow
              label="Embedding"
              value={asset.status === "READY" ? "✅ Generated" : asset.status === "PROCESSING" ? "⏳ Processing" : "❌ Not generated"}
            />
            <MetadataRow label="Model" value="clip-ViT-B-32" mono />
            <MetadataRow label="Dimensions" value="512" mono />
          </MetadataSection>
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
                  badgeLabel = "Near Duplicate";
                  badgeClass = "bg-purple-500/20 text-purple-400 border border-purple-500/30";
                } else if (pct >= 95) {
                  badgeLabel = "Extremely Similar";
                  badgeClass = "bg-red-500/20 text-red-400 border border-red-500/30";
                } else if (pct >= 90) {
                  badgeLabel = "Very Similar";
                  badgeClass = "bg-orange-500/20 text-orange-400 border border-orange-500/30";
                } else if (pct >= 80) {
                  badgeLabel = "Similar";
                  badgeClass = "bg-green-500/20 text-green-400 border border-green-500/30";
                }

                return (
                  <Link
                    key={sim.image.id}
                    href={`/media/${sim.image.id}`}
                    className="group relative aspect-square rounded-lg overflow-hidden border border-default transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-md hover:scale-[1.02]"
                    style={{ backgroundColor: "var(--bg-tertiary)" }}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={getThumbnailUrl(sim.image.id)}
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
