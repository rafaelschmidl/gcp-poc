-- Minimal BQML example: k-means clustering on article/day by views
-- Not predictive, but demonstrates training pipeline
CREATE OR REPLACE MODEL `{{PROJECT_ID}}.models.article_kmeans`
OPTIONS(
  model_type = 'kmeans',
  num_clusters = 2
) AS
SELECT
  CAST(UNIX_SECONDS(TIMESTAMP(view_date)) AS FLOAT64) AS ts,
  SAFE.LOG(1 + views) AS log_views
FROM `{{PROJECT_ID}}.mart.article_daily`;


