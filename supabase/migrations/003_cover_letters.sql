-- Migration: 003_cover_letters
-- Description: Create cover_letters table

CREATE TABLE IF NOT EXISTS cover_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    
    -- Ensure only one cover letter per job and profile combination
    CONSTRAINT unique_cover_letter UNIQUE (job_id, profile_id)
);
