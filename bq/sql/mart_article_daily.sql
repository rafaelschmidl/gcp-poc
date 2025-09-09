-- Creates a simple mart view with daily pageviews per article
-- Replace {{PROJECT_ID}} if executing via file; our automation runs inline with bq
CREATE OR REPLACE VIEW `{{PROJECT_ID}}.mart.article_daily` AS
SELECT
  view_date,
  article,
  SUM(views) AS views
FROM `{{PROJECT_ID}}.raw.wikipedia_pageviews`
GROUP BY view_date, article;


