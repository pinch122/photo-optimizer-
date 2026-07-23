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

export type AnalysisStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED_NO_PROVIDER";

export interface AIAnalysis {
  // Processing lifecycle
  processing_status: AnalysisStatus | null;
  processed_at: string | null;
  model_name: string | null;

  // Visual understanding
  caption: string | null;
  detailed_description: string | null;
  scene: string | null;
  objects: string[] | null;
  activities: string[] | null;

  // Image understanding
  indoor_outdoor: string | null;
  is_indoor: boolean | null;        // legacy
  weather: string | null;
  season: string | null;
  dominant_colors: string[] | null;

  // People
  people_count: number | null;

  // Documents / OCR
  detected_text: string | null;
  document_type: string | null;

  // Memory understanding
  event_type: string | null;
  travel_event: boolean | null;
  location_guess: string | null;
  estimated_location: string | null; // legacy
  mood: string | null;
  keywords: Record<string, any> | null;

  // AI metadata
  ai_confidence: number | null;
}

export interface QualityAssessment {
  id?: string;
  overall_score?: number | null;
  quality_grade?: string | null;
  sharpness_score?: number | null;
  blur_score?: number | null;
  exposure_score?: number | null;
  brightness_score?: number | null;
  aesthetic_score?: number | null;
  resolution_score?: number | null;
  confidence?: number | null;
  issues?: string[] | null;
  recommendation?: string | null;
  provider_versions?: Record<string, string> | null;
  provider_scores?: Record<string, any> | null;
  evaluated_at?: string | null;
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
  is_deleted?: boolean;
  deleted_at?: string | null;
  deleted_from?: string | null;
  remaining_days?: number | null;
  photo_metadata: PhotoMetadata | null;
  p_hash: string | null;
  ai_analysis: AIAnalysis | null;
  quality_assessment?: QualityAssessment | null;
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
  match_type?: string;
  photo_metadata: PhotoMetadata | null;
  p_hash: string | null;
  explanation: string[] | null;
  ai_analysis: AIAnalysis | null;
  quality_assessment?: QualityAssessment | null;
}

export interface SearchResponse {
  items: SearchResult[];
  excellent_matches?: SearchResult[];
  similar_photos?: SearchResult[];
  total: number;
  total_similar?: number;
  limit: number;
  offset: number;
  message?: string | null;
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
