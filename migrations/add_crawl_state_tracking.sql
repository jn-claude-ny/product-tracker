-- Add crawl state tracking fields to websites table

-- Add crawl_state column
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS crawl_state VARCHAR(20) DEFAULT 'never_crawled' NOT NULL;

-- Add total_products_expected column
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS total_products_expected INTEGER DEFAULT 0;

-- Add products_discovered column
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS products_discovered INTEGER DEFAULT 0;

-- Add products_processed column
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS products_processed INTEGER DEFAULT 0;

-- Add last_crawl_completed_at column
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS last_crawl_completed_at TIMESTAMP;

-- Update existing websites to set proper state based on current data
UPDATE websites 
SET crawl_state = CASE 
    WHEN is_crawling = true THEN 'crawling'
    WHEN sitemap_last_checked IS NOT NULL THEN 'completed'
    ELSE 'never_crawled'
END
WHERE crawl_state = 'never_crawled';

-- Create index on crawl_state for faster queries
CREATE INDEX IF NOT EXISTS idx_websites_crawl_state ON websites(crawl_state);

-- Add comment
COMMENT ON COLUMN websites.crawl_state IS 'Current crawl state: never_crawled, crawling, paused, completed, failed';
