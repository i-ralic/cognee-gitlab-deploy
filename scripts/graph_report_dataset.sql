-- Per-dataset graph counts (postgres_demo tables). Run with -v ds=<dataset_id>:
--   docker compose exec -T postgres psql -U cognee -d cognee_db -v ds=<dataset_id> -f - < scripts/graph_report_dataset.sql
-- The dataset_id is printed by the sync ("dataset_id=...") and stored in datasets.id.
\echo == nodes by type in this dataset
SELECT type, count(*) AS n FROM graph_node WHERE :'ds' = ANY(source_dataset_ids) GROUP BY type ORDER BY n DESC;
\echo == totals in this dataset (edges: both ends in the dataset)
WITH n AS (SELECT id FROM graph_node WHERE :'ds' = ANY(source_dataset_ids))
SELECT (SELECT count(*) FROM n) AS nodes,
       (SELECT count(*) FROM graph_edge e WHERE e.source_id IN (SELECT id FROM n) AND e.target_id IN (SELECT id FROM n)) AS edges;
\echo == entity-entity relations in this dataset (excluding structural edges)
WITH n AS (SELECT id, type FROM graph_node WHERE :'ds' = ANY(source_dataset_ids))
SELECT count(*) FROM graph_edge e JOIN n s ON s.id=e.source_id JOIN n t ON t.id=e.target_id
WHERE s.type NOT IN ('DocumentChunk','TextDocument','TextSummary') AND t.type NOT IN ('DocumentChunk','TextDocument','TextSummary')
  AND e.relationship_name NOT IN ('contains','is_part_of','is_a','made_from','exists_in');
