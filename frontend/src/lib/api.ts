import axios from "axios";
import type {
  MediaAsset,
  UploadResponse,
  StatusResponse,
  SearchResponse,
  HealthResponse,
  MediaListResponse,
} from "./types";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
});

// ─── Health ────────────────────────────────────────────────────────
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

// ─── Media ─────────────────────────────────────────────────────────
export async function uploadMedia(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<UploadResponse>("/media/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getMediaStatus(id: string): Promise<StatusResponse> {
  const { data } = await api.get<StatusResponse>(`/media/${id}/status`);
  return data;
}

export async function getMediaDetail(id: string): Promise<MediaAsset> {
  const { data } = await api.get<MediaAsset>(`/media/${id}`);
  return data;
}

export async function reprocessMedia(id: string): Promise<StatusResponse> {
  const { data } = await api.post<StatusResponse>(`/media/${id}/reprocess`);
  return data;
}

// ─── Search ────────────────────────────────────────────────────────
export async function searchMedia(
  query: string,
  limit: number = 12,
  offset: number = 0
): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>("/media/search", {
    params: { q: query, limit, offset },
  });
  return data;
}

export async function listMedia(
  limit: number = 30,
  offset: number = 0
): Promise<MediaListResponse> {
  const { data } = await api.get<MediaListResponse>("/media", {
    params: { limit, offset },
  });
  return data;
}

export async function deleteMedia(id: string): Promise<{ message: string }> {
  const { data } = await api.delete<{ message: string }>(`/media/${id}`);
  return data;
}

export interface SimilarImage {
  image: MediaAsset;
  filename: string;
  score: number;
  similarity_percentage: number;
}

export async function getSimilarMedia(
  id: string,
  limit: number = 20
): Promise<SimilarImage[]> {
  const { data } = await api.get<SimilarImage[]>(`/media/${id}/similar`, {
    params: { limit },
  });
  return data;
}

// ─── File URLs ─────────────────────────────────────────────────────
export function getThumbnailUrl(id: string): string {
  return `${API_BASE_URL}/api/media/${id}/file?size=thumbnail`;
}

export function getOriginalUrl(id: string): string {
  return `${API_BASE_URL}/api/media/${id}/file?size=original`;
}

export default api;
