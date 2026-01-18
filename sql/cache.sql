-- Create cache table
CREATE TABLE IF NOT EXISTS nl2sql_cache (
    cache_key VARCHAR(500) PRIMARY KEY,
    sql_query TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    use_count INTEGER DEFAULT 1,
    created_by VARCHAR(100),
    metadata JSONB
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_nl2sql_cache_last_used 
ON nl2sql_cache(last_used);

-- Verify tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('deployment_data', 'test_data', 'nl2sql_cache');