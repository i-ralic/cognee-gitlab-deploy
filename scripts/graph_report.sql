-- Part 3 graph statistics, straight from the postgres_demo tables (graph_node, graph_edge).
-- Run: docker compose exec -T postgres psql -U cognee -d cognee_db -f - < scripts/graph_report.sql
\echo '== node types'
SELECT type, count(*) AS n FROM graph_node GROUP BY type ORDER BY n DESC;
\echo '== edge types'
SELECT relationship_name, count(*) AS n FROM graph_edge GROUP BY relationship_name ORDER BY n DESC;
\echo '== totals'
SELECT (SELECT count(*) FROM graph_node) AS nodes, (SELECT count(*) FROM graph_edge) AS edges;
\echo '== ten most connected nodes (degree, excluding structural chunk/document nodes)'
SELECT n.name, n.type, d.degree
FROM (
  SELECT id, count(*) AS degree FROM (
    SELECT source_id AS id FROM graph_edge UNION ALL SELECT target_id FROM graph_edge
  ) x GROUP BY id
) d JOIN graph_node n ON n.id = d.id
WHERE n.type NOT IN ('DocumentChunk', 'TextDocument', 'TextSummary', 'DataPoint')
ORDER BY d.degree DESC LIMIT 10;
\echo '== sample of extracted entity-entity relations with their source chunk text'
-- Entity edges carry the chunk they came from in provenance; join back to the chunk text.
SELECT s.name AS head, e.relationship_name AS rel, t.name AS tail,
       left(c.properties->>'text', 240) AS source_text
FROM graph_edge e
JOIN graph_node s ON s.id = e.source_id
JOIN graph_node t ON t.id = e.target_id
LEFT JOIN graph_edge ce ON ce.target_id = s.id AND ce.relationship_name = 'contains'
LEFT JOIN graph_node c ON c.id = ce.source_id AND c.type = 'DocumentChunk'
WHERE s.type NOT IN ('DocumentChunk','TextDocument','TextSummary') AND t.type NOT IN ('DocumentChunk','TextDocument','TextSummary')
  AND e.relationship_name NOT IN ('contains','is_part_of','is_a','made_from','exists_in')
ORDER BY random() LIMIT 30;
