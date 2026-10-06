# Report: what ended up in the graph, and what did not

**BLUF.** 134 issues and merge requests of the public GitLab project `inkscape/vectors/content` went into cognee 1.6.2 with no LLM key: 1,364 nodes, 3,340 edges, of which only 253 (7.6 %) are entity-to-entity relations. The hubs are the project, two authors and boilerplate. Three of the five wrong relations come from the document header the connector renders, so the first change is the connector's document shape, not the extractor. Edit / add / delete re-synced exactly (2 changed, 1 deleted, third sync a no-op), on a seeded project and again offline. Corpus, method, re-sync tables, caveats, resources: [APPENDIX.md](APPENDIX.md).

## 1. Node types and edge types, with counts

| Node type | Count | | Edge type | Count |
|---|---|---|---|---|
| Entity | 886 | | contains (chunk → entity) | 1,763 |
| DocumentChunk | 161 | | is_a (entity → type) | 1,002 |
| TextSummary | 161 | | made_from / is_part_of (structure) | 161 + 161 |
| TextDocument | 134 | | entity–entity relations, 17 names | **253** |
| EntityType | 22 | | part_of 36 · uses 36 · created_by 27 · participates_in 26 · works_for 25 · founded_by 22 · produces 15 · leads 14 · occurred_on 14 · collaborates_with 10 · owns 8 · five more ≤ 7 | |
| **Total nodes** | **1,364** | | **Total edges** | **3,340** |

Entities per type (`is_a` counts): person 117, organization 104, concept 100, software 97, date
82, document 77, event 74, technology 72, then a tail. Open label bank here; the seeded run in the
appendix used the closed `ontology/gitlab.owl`.

## 2. The ten most connected nodes

| Node | Type | Degree | Verdict |
|---|---|---|---|
| inkscape | Entity | 162 | Meaningful: in almost every document (81 `contains`, 21 `uses`, 17 `part_of`). |
| person, organization, concept, software, date, document, event, technology | EntityType | 117 · 104 · 100 · 97 · 82 · 77 · 74 · 72 | Structural: one `is_a` edge per entity. Correct as types, noise for navigation; `concept` is a dumping ground ("headings", "momentum"). |
| twitter | Entity | 64 | Half meaningful: 51 of 64 edges come from the "Publication Channels" checklist most issues carry. |

Eight of ten hubs are type nodes, an artefact of modelling `is_a` as edges; among real entities
`inkscape` and `twitter` lead, then `website` and the two most active authors.

## 3. Five correct and five wrong relationships, with the source text

**Correct**

| Relation | Source text (chunk) |
|---|---|
| jason harder `uses` inkscape | "Jason Harder uses Inkscape for creating professional print materials." |
| hellotux `produces` shirts | "Hellotux sells shirts, where a small part of the income goes to Inkscape" |
| bryce harrington `collaborates_with` nathan hurst | "Bryce Harrington, one of the four original founders … along with Ted Gould, Nathan Hurst" (#98) |
| inkscape `participates_in` libre graphic meeting 2025 | "The annual LibreGraphics Meeting (LGM) conference 2025 will take place in may" (#118) |
| vectorstock `owns` platinum pen | "VectorStock is a new Inkscape Platinum Sponsor ('Platinum Pen')" (#22) |

**Wrong**

| Relation | Source text | What went wrong |
|---|---|---|
| inkscape `founded_by` ryangorley | #2 "Article: Submitting First Pull Request … Author: ryangorley" | Author line read as founder. |
| red hat `founded_by` ryangorley | #11 "Red Hat Hosting 2018 Inkscape Hackfest in Boston … Author: ryangorley" | Same: Red Hat founded by a volunteer. |
| christopher rogers `headquartered_in` paris | "Christopher Rogers … made his first pull request during the Hackfest in Paris" | No `attended` in the bank; nearest location verb forced. |
| twitter `part_of` inkscape extension manager | "## Publication Channels * [x] Website * [x] Twitter post" | A channel checklist became part-of the release. |
| ryangorley `works_for` pia | #8 "Private Internet Access (PIA) has proudly joined … corporate sponsors … Author: ryangorley" | Article author became the sponsor's employee. |

Pattern: three of five errors come from the **document header I render** (`Author:`, `State:`).

## 4. What the extraction missed that a reader would expect

- **Dates not linked to events.** 82 `date` entities, 14 `occurred_on` edges; "Inkscape 1.0.1
  will be released in early September 2020" gave `inkscape 1.0.1` and a date, no edge.
- **Sponsorship.** The corpus is about sponsors (PIA, VectorStock, Red Hat); the open bank has no
  `sponsors`, so it surfaces as `owns`, `produces`, `participates_in`, or not at all.
- **State and labels.** `State: closed`, `Labels: Published` reach no node, so "which articles were
  published" is not a graph question.
- **Comments.** Off in this run (token).
- **Identity.** `inkscape`, `inkscape project`, `inkscape vectors team` are separate nodes;
  `moini`/`Moini` are not merged, so the degrees undercount the hubs.

## 5. Three questions the graph can answer and three it cannot

All via `POST /api/v1/search`, `searchType: CHUNKS`, `topK: 5` (`scripts/ask.sh`).

**Answered (fact in the top-5 chunks)**

1. *Who hosted the 2018 Inkscape Hackfest in Boston?* → chunk 1: "Red Hat Hosting 2018 Inkscape Hackfest in Boston".
2. *Which company became a Platinum sponsor of Inkscape?* → chunk 1: "VectorStock is a new Inkscape Platinum Sponsor".
3. *When will Inkscape 1.0.1 be released?* → chunk 1: "released in early September 2020."

**Not answered**

4. *How many issues are still open?* → five unrelated closed issues; `state` is not in the graph.
5. *Who are the four original founders of Inkscape?* → the right article at chunk 1, but the naming sentence is in a later chunk; the graph has `collaborates_with` but no `founder_of`.
6. *Which merge requests changed the bug migration badges?* → the right MR, but only by title words; no node for the file or the change. A text match, not a graph answer.

`GRAPH_COMPLETION` needs an LLM key; `CYPHER` is not available on `postgres_demo`.

## 6. The one change I would make first

**Change the connector's document shape** before labels, ontology or chunking: move `Author`,
`State`, `Labels`, branch names and the "Publication Channels" checklist out of `content` into row
columns emitted as structured facts. It is the single root cause of three of five wrong relations,
of the `twitter` hub and of the two unanswerable state questions; one afternoon in the connector,
zero in cognee. The closed ontology that adds `sponsors` and `released_on` already ships and was
used for the seeded run; it fixed the missing relation types, not the header problem.

