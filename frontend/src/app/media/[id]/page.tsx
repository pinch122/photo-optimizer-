"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMediaDetail, getThumbnailUrl, getOriginalUrl, reprocessMedia } from "@/lib/api";
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

  const { data: asset, isLoading, error } = useQuery({
    queryKey: ["media", id],
    queryFn: () => getMediaDetail(id),
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
            <MetadataRow label="Type" value={asset.mime_type} mono />
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
