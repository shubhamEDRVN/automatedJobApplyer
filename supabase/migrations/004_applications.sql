-- Migration: 004_applications
-- Description: Add application tracking columns to jobs table

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS apply_method TEXT,
ADD COLUMN IF NOT EXISTS apply_status TEXT;
