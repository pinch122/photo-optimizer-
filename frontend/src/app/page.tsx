"use client";

import { useQuery } from "@tanstack/react-query";
import { searchMedia, getHealth } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import StatCard from "@/components/dashboard/StatCard";
import QuickActions from "@/components/dashboard/QuickActions";
import RecentUploads from "@/components/dashboard/RecentUploads";
import Link from "next/link";
import { Image, Brain, HardDrive, CheckCircle2, Upload } from "lucide-react";

export default function DashboardPage() {
  // Fetch recent uploads via search API
  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ["recent-uploads"],
    queryFn: () => searchMedia("photo", 6, 0),
  });

  // Fetch health status
  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30000,
  });

  // Derive stats from search data
  const totalPhotos = recentData?.total ?? 0;
  const totalSize = recentData?.items?.reduce((sum, item) => sum + item.file_size, 0) ?? 0;
  const readyCount = recentData?.items?.filter((i) => i.status === "READY").length ?? 0;
  const readyRate = recentData?.items?.length
    ? Math.round((readyCount / recentData.items.length) * 100)
    : 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Your PhotoMind AI command center"
        actions={
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium text-white bg-brand hover:bg-brand-hover transition-colors duration-150"
          >
            <Upload className="w-4 h-4" />
            Upload
          </Link>
        }
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        <StatCard
          title="Total Photos"
          value={totalPhotos.toLocaleString()}
          subtitle="In your library"
          icon={Image}
          iconColor="var(--accent-primary)"
          loading={recentLoading}
        />
        <StatCard
          title="Embeddings"
          value={readyCount.toLocaleString()}
          subtitle="AI-indexed photos"
          icon={Brain}
          iconColor="#8B5CF6"
          loading={recentLoading}
        />
        <StatCard
          title="Storage Used"
          value={formatFileSize(totalSize)}
          subtitle="Original files"
          icon={HardDrive}
          iconColor="var(--warning)"
          loading={recentLoading}
        />
        <StatCard
          title="Ready Rate"
          value={`${readyRate}%`}
          subtitle="Processing completion"
          icon={CheckCircle2}
          iconColor="var(--success)"
          loading={recentLoading}
        />
      </div>

      {/* Recent Uploads */}
      <div className="mb-8">
        <RecentUploads items={recentData?.items ?? []} loading={recentLoading} />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
          Quick Actions
        </h2>
        <QuickActions />
      </div>
    </>
  );
}
