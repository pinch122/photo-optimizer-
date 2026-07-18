-- ============================================================
-- Migration: Sprint 5/6 — ImageAIAnalysis schema expansion
-- Applied: 2026-07-16
-- Database: photomind (PostgreSQL 15)
-- ============================================================
-- Adds all Knowledge Record columns introduced in Sprint 5 and
-- Sprint 6. Every new column is nullable to preserve existing rows.
-- The retry_count and processing_status columns have NOT NULL
-- defaults (0 and 'SKIPPED_NO_PROVIDER' respectively).
-- ============================================================

-- Processing lifecycle
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS processing_status VARCHAR(30) NOT NULL DEFAULT 'SKIPPED_NO_PROVIDER';
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS model_version VARCHAR(100);

-- Visual understanding
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS detailed_description VARCHAR(4000);

-- Image understanding
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS indoor_outdoor VARCHAR(20);
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS dominant_colors JSON;

-- People
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS people_count INTEGER;

-- Documents / OCR
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS detected_text VARCHAR(8000);
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS document_type VARCHAR(100);

-- Memory understanding
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS event_type VARCHAR(100);
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS travel_event BOOLEAN;
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS location_guess VARCHAR(255);

-- AI metadata
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS raw_response JSON;
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE image_ai_analysis ADD COLUMN IF NOT EXISTS error_message VARCHAR(2000);

-- Index on processing_status for efficient status-based filtering
CREATE INDEX IF NOT EXISTS ix_image_ai_analysis_processing_status ON image_ai_analysis(processing_status);

-- Backfill: rows with a caption were written by the old pipeline — mark COMPLETED
UPDATE image_ai_analysis
SET processing_status = 'COMPLETED',
    processed_at = analysis_timestamp
WHERE caption IS NOT NULL
  AND processing_status = 'SKIPPED_NO_PROVIDER';
