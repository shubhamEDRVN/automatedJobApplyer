-- Migration: 002_jobs
-- Description: Create jobs table

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    apply_url TEXT,
    source TEXT,
    posted_date TIMESTAMP WITH TIME ZONE,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    status TEXT DEFAULT 'new',
    
    -- Unique constraint to prevent duplicate jobs from being inserted
    -- ON CONFLICT DO NOTHING will use this constraint
    CONSTRAINT unique_job_title_company UNIQUE (title, company)
);
