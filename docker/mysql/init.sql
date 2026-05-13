-- ============================================================
-- PA Review Platform — MySQL Initialization Script
-- Runs once on first container start
-- ============================================================

CREATE DATABASE IF NOT EXISTS pa_review_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Grant all privileges to the application user
GRANT ALL PRIVILEGES ON pa_review_db.* TO 'pa_user'@'%';
FLUSH PRIVILEGES;
