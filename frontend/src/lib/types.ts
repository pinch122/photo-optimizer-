export type MediaType = "PHOTO" | "VIDEO" | "DOCUMENT" | "AUDIO";
export type AssetStatus = "UPLOADED" | "PROCESSING" | "READY" | "FAILED";

export interface PhotoMetadata {
  width: number;
  height: number;
  camera_make: string | null;
  camera_model: string | null;
  exposure_time: string | null;
  f_number: string | null;
  iso_speed: number | null;
  gps_latitude: number | null;
  gps_longitude: number | null;
}

export interface MediaAsset {
  id: string;
  filename: string;
  mime_type: string;
  media_type: MediaType;
  file_size: number;
  status: AssetStatus;
  taken_at: string;
  created_at: string;
  photo_metadata: PhotoMetadata | null;
  p_hash: string | null;
}

export interface UploadResponse {
  id: string;
  filename: string;
  media_type: MediaType;
  file_size: number;
  status: AssetStatus;
  created_at: string;
}

export interface StatusResponse {
  id: string;
  status: AssetStatus;
  error_message: string | null;
}

export interface SearchResult {
  id: string;
  filename: string;
  mime_type: string;
  media_type: MediaType;
  file_size: number;
  status: AssetStatus;
  taken_at: string;
  created_at: string;
  score: number;
  photo_metadata: PhotoMetadata | null;
  p_hash: string | null;
}

export interface SearchResponse {
  items: SearchResult[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: string;
}

export interface MediaListResponse {
  items: MediaAsset[];
  total: number;
  limit: number;
  offset: number;
}

