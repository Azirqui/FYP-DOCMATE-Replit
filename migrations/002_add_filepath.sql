-- Migration: Add file_path column to project_files
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- Add file_path column to store the full relative path (e.g., src/utils/helpers.py)
ALTER TABLE project_files
ADD COLUMN IF NOT EXISTS file_path TEXT;

-- Backfill existing rows: set file_path to filename for rows that don't have it
UPDATE project_files
SET file_path = filename
WHERE file_path IS NULL;
