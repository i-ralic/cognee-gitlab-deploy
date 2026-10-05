# Report: what ended up in the graph, and what did not

## Corpus and method

- **Source:** the public GitLab project `inkscape/vectors/content` (the Inkscape marketing team's
  content tracker): **117 issues + 17 merge requests = 134 documents**, comments off (the notes
  endpoint needs a token on gitlab.com; the board's own project will add them). Real text, written
  by real people, about releases, hackfests, sponsors, articles and videos.
- **Sync 1:** 134 documents in 282 s. **Sync 2 (no changes upstream):** 0 changed, 0 deleted, 9 s,
  graph identical; the cursor and id set were restored in a fresh container from dlt state in
  Postgres (`dlt_database_gitlab_project.gitlab_project._dlt_pipeline_state`).
- **Extraction:** cognee 1.6.2 GLiNER demo (`fastino/gliner2.5-base-v1`), closed label bank
  filtered per document; embeddings `BAAI/bge-small-en-v1.5` via fastembed; no LLM key anywhere.
- **Counting:** `scripts/graph_report.sql` against the `postgres_demo` tables `graph_node` /
  `graph_edge`. **"Answered"** means the fact is readable in the top-5 chunks `recall()` returns;
  without an LLM there is no generated answer to grade.
- **Not available here:** `GlinerRunStats` (candidate vs kept vs dropped edges) only exists when
  the GLiNER tasks are run through `run_custom_pipeline`; `remember()` does not expose it. I did not
  spend the budget wiring a second pipeline for one counter.

## 1. Node types and edge types, with counts

| Node type | Count | | Edge type | Count |
|---|---|---|---|---|
| Entity | 886 | | contains (chunk → entity) | 1,763 |
| DocumentChunk | 161 | | is_a (entity → type) | 1,002 |
| TextSummary | 161 | | made_from / is_part_of (structure) | 161 + 161 |
| TextDocument | 134 | | part_of, uses | 36, 36 |
| EntityType | 22 | | created_by, participates_in, works_for, founded_by | 27, 26, 25, 22 |
| **Total nodes** | **1,364** | | produces, leads, occurred_on, collaborates_with | 15, 14, 14, 10 |
| | | | owns, headquartered_in, located_in, member_of, acquired | 8, 7, 6, 5, 2 |
| | | | **Total edges** | **3,340** |

Only **253 of 3,340 edges (7.6 %)** are entity-to-entity relations; the rest is structure
(chunk contains entity, entity is_a type, document/summary scaffolding). Entity types used:
person 117, organization 104, concept 100, software 97, date 82, document 77, event 74,
technology 72, product 59, role 49, location 47, project 35, time_period 24, quantity 24,
programming_language 18, money 9, then a tail of 3 or fewer (industry, percentage, award, food,
facility, nationality).

## 2. The ten most connected nodes

| Node | Type | Degree | Verdict |
|---|---|---|---|
| inkscape | Entity | 162 | Meaningful: the project is in almost every document (81 `contains` edges, 21 `uses`, 17 `part_of`). |
| person | EntityType | 117 | Structural (one `is_a` per person entity). Noise for navigation, correct as a type. |
| organization | EntityType | 104 | Structural. |
| concept | EntityType | 100 | Structural, and a dumping ground: "headings", "branding", "momentum". |
| software | EntityType | 97 | Structural. |
| date | EntityType | 82 | Structural; the dates themselves are rarely linked to events (see §4). |
| document | EntityType | 77 | Structural. |
| event | EntityType | 74 | Structural. |
| technology | EntityType | 72 | Structural. |
| twitter | Entity | 64 | Half meaningful: 51 of 64 edges are `contains` from the "Publication Channels" checklist that most issues carry. It says nothing about any issue. |

Eight of the ten hubs are the type nodes, which is an artefact of modelling `is_a` as graph edges.
Among real entities, `inkscape` and `twitter` lead, followed by `website`, `moini`, `ryangorley`
(the two most active authors). The hubs are the project, the team, and the boilerplate.

## 3. Five correct and five wrong relationships, with the source text

**Correct**

| Relation | Source text (chunk) |
|---|---|
| jason harder `uses` inkscape | "Jason Harder uses Inkscape for creating professional print materials." (issue, Moini) |
| hellotux `produces` shirts | "Hellotux sells shirts, where a small part of the income goes to Inkscape" |
| bryce harrington `collaborates_with` nathan hurst | "Bryce Harrington, one of the four original founders of the Inkscape Project … along with Ted Gould, Nathan Hurst, and Me…" (#98) |
| inkscape `participates_in` libre graphic meeting 2025 | "The annual LibreGraphics Meeting (LGM) conference 2025 will take place in may" (#118) |
| vectorstock `owns` platinum pen | "VectorStock is a new Inkscape Platinum Sponsor ('Platinum Pen')" (#22). Defensible: the sponsor tier is theirs. |

**Wrong**

| Relation | Source text | What went wrong |
|---|---|---|
| inkscape `founded_by` ryangorley | #2 "Article: Submitting First Pull Request … Author: ryangorley" | The issue *author* line was read as the project's founder. Metadata header leaked into relations. |
| red hat `founded_by` ryangorley | #11 "Red Hat Hosting 2018 Inkscape Hackfest in Boston … Author: ryangorley" | Same failure, worse: Red Hat founded by a volunteer. |
| christopher rogers `headquartered_in` paris | "Christopher Rogers … made his first pull request during the Hackfest in Paris" | A person is not headquartered; the relation bank has no `attended`, so the nearest location verb was forced. |
| twitter `part_of` inkscape extension manager | "## Publication Channels * [x] Website * [x] Twitter post (@zigzagmlt…)" | A checklist of channels in a release issue became a part-of relation to the release's subject. |
| ryangorley `works_for` pia | #8 "Private Internet Access (PIA) has proudly joined the family of corporate sponsors … Author: ryangorley" | Author of an article about a sponsor became the sponsor's employee. |

Pattern: three of the five errors come from the **document header I render** (`Author: …`,
`State: …`) sitting next to the title in the first chunk. The extractor cannot tell an issue's
author from the subject's actors.

## 4. What the extraction missed that a reader would expect

- **Dates are nodes but not linked to what happened.** 82 `date` entities, 14 `occurred_on` edges.
  "Inkscape 1.0.1 will be released in early September 2020" produced the entity `inkscape 1.0.1`
  and a date, but no edge between them.
- **Sponsorship as a relation.** The corpus is largely about sponsors (PIA, VectorStock, Betrugstest,
  Red Hat hosting). There is no `sponsors` relation in the bank, so sponsorship appears as `owns`,
  `produces`, `participates_in`, or not at all.
- **Issue state and labels.** Every document says `State: closed` and `Labels: Published`; none of
  that reaches the graph. A reader expects "which articles were published" to be a graph question.
- **Comments.** Off in this run (token). Half of the human reasoning on these issues is in them.
- **Cross-document identity.** `inkscape`, `inkscape project`, `inkscape vectors`,
  `inkscape vectors team` are four nodes; `moini` and `Moini`, `crogers` / `christopher rogers` /
  `c.rogers` are not merged. Degree numbers above undercount the real hubs for this reason.

## 5. Three questions the graph can answer and three it cannot

All run as `POST /api/v1/search` with `searchType: CHUNKS`, `topK: 5` (`scripts/ask.sh`).

**Answered (fact in the top-5 chunks)**

1. *Who hosted the 2018 Inkscape Hackfest in Boston?* → chunk 1: "Red Hat Hosting 2018 Inkscape Hackfest in Boston". Yes.
2. *Which company became a Platinum sponsor of Inkscape?* → chunks 1–2: "VectorStock is a new Inkscape Platinum Sponsor". Yes.
3. *When will Inkscape 1.0.1 be released?* → chunk 1: "Inkscape 1.0.1 will be released in early September 2020." Yes.

**Not answered**

4. *How many issues are still open?* → five unrelated closed issues. An aggregate over state;
   neither chunks nor a GLiNER graph can count, and `state` is not in the graph.
5. *Who are the four original founders of Inkscape?* → the retirement article is chunk 1, but the
   sentence naming the four is in a later chunk of the same document, not in the top 5. The
   graph has `bryce harrington collaborates_with nathan hurst / ted gould` but no `founder_of`.
6. *Which merge requests changed the bug migration badges?* → chunk 1 is the right MR
   (`!2 Update media/bug_migration/bug_badges_medalions.svg`) but only because its title matches
   the words; the graph has no node for the file or the change, so "which MRs touched X" is a
   text match, not a graph answer. Counted as not answered by the graph.

`GRAPH_COMPLETION` returns `LLMAPIKeyNotSetError` in this deployment, as expected; `CYPHER` is not
supported by `postgres_demo`.

## 6. The one change I would make first

**Change the connector's document shape**, before touching labels, ontology or chunking: move the
metadata (`Author`, `State`, `Labels`, branch names, the "Publication Channels" checklist) out of
`content` and into row columns, and emit them as structured facts instead of prose. Reason: it is
the single root cause of three of the five wrong relations (author read as founder/employee), of the
`twitter` noise hub, and of the two unanswerable state questions. It costs one afternoon in the
connector and zero in cognee. Labels or an ontology would be the second change, because
`sponsors` and `released_on` are the two missing relation types this corpus actually needs, and a
small OWL file (`ONTOLOGY_FILE_PATH`) gives the GLiNER demo exactly those.

## Appendix: the second sync with an edit, an add and a delete

Done on a project I own, `collabwriting-app/cognee-corpus`, seeded by `scripts/seed_gitlab.py`
from the same public tracker: **19 issues + 5 merge requests = 24 documents, comments on**, so
documents are up to 33 KB (the first corpus maxed at 4.8 KB). Dataset `gitlab_corpus`, schema
from `ontology/gitlab.owl` (see README "Decisions"; the first corpus used the open label bank).
Counts are for nodes tagged with this dataset; entity nodes shared with the first dataset
(`inkscape`, `twitter`, ...) carry that dataset's edges too, which is why relation names outside
the ontology appear. The deltas are what matter.

| | Sync 1 (fresh) | `mutate_corpus.py` | Sync 2 | Sync 3 |
|---|---|---|---|---|
| Connector log | 19 + 5 changed, 0 deleted | edit #4, add #20, delete #18 | **Issue: 2 changed, 1 deleted** | 0 changed, 0 deleted |
| Wall / peak RSS | 125 s / 4.5 GiB | | 15 s / 3.0 GiB | 5 s |
| TextDocument | 24 | | 24 (−1 deleted, +1 added, edited one re-hashed) | 24 |
| DocumentChunk / TextSummary | 93 / 93 | | 92 / 92 | 92 |
| Entity | 574 | | 573 | 573 |
| Nodes / edges | 793 / 2,601 | | **790 / 2,563** | 790 / 2,563 |

**What the graph did with each change** (SQL on `graph_node` / `graph_edge`):

- **Delete** (issue #18, "Article - Bryce's Retirement Announcement"): the connector's id sweep
  emitted one `_deleted` row; cognee logged *"Deleting 2 orphaned dlt row(s)"* (the deleted issue
  and the pre-edit version of #4, whose content hash changed) and removed the orphaned chunks,
  summaries and edge types. Chunks containing that title in this dataset: **0**. The copy of the
  same article in the first dataset (#98) is still there, and still comes back from `recall()`,
  because search in this deployment does not honour the `datasets` filter with access control off
  (one user, all datasets). That is a finding, not a bug in the connector.
- **Add** (issue #20, marker "the Quokka palette ships with Inkscape 1.5 and was drawn by Mira
  Kovac"): one new document, one chunk; graph: `quokka palette is_a feature`, `mira kovac is_a
  person`, and one wrong edge, `quokka palette released_on 20261005-1013` (GLiNER read the marker's
  timestamp as a date). `recall()` for the sentence: **rank 1**.
- **Edit** (issue #4, marker "the Zagreb Hackfest 2026 is hosted by Collabwriting at the Lauba
  hall" appended to a 4.9 KB description): the connector re-fetched it (`updated_at` moved), cognee
  replaced the document. Graph: `collabwriting hosts zagreb hackfest 2026`, `zagreb hackfest 2026
  held_in lauba hall`, `held_in zagreb`, `lauba hall is_a location`, plus an over-read
  `collabwriting sponsors zagreb hackfest 2026`. `recall()` for the literal sentence: rank 2; for
  *"Where is the Zagreb Hackfest 2026 held?"*: **not in the top 5**. The fact is in the graph but
  sits at the end of a chunk whose embedding is about something else; `CHUNKS` search cannot
  reach it and `GRAPH_COMPLETION` needs an LLM. Same lesson as section 6: a fact buried in a long
  issue body is a graph fact, not a retrievable chunk.

**What this run changed in the deployment** (README "Resources"): the defaults OOM-killed the
sync three times on these longer documents. Root cause measured, not guessed: 2.7 GiB process
baseline + ~250 MiB per chunk scored in one GLiNER pass, and cognee sends every chunk of a
document in one call. `SYNC_CHUNKS_PER_BATCH=4` and the closed schema fixed it. The connector-side
follow-up landed in PR 1 as `GITLAB_MAX_CONTENT_CHARS` (default 32,000 characters, 0 = off):
header and description first, comments oldest-first while they fit, a closing line with the
omitted count, deterministic so the content hash stays stable. One issue with a 200-comment
thread can no longer dictate the memory limit of the whole deployment. The numbers above were
measured before the cap; with it, the longest document here (33 KB) loses its last comments.

**Reproducibility caveat.** A few hours after the seed and mutate runs, gitlab.com blocked the
account that owns `collabwriting-app/cognee-corpus` (every authenticated call returns
`403 Your account has been blocked`), and the project's issues and merge requests now list as
empty for anonymous readers, although the project page itself still resolves. The seed script
created 19 issues, 5 branches, 5 merge requests and their comments within minutes on a fresh
account, which is the pattern GitLab's anti-abuse checks look for `[unverified: GitLab does not
state the reason]`. The main corpus (`inkscape/vectors/content`, sections 1 to 6) is a public
project and reproduces as described. To re-run this appendix, seed a project under an
established account and pace the seed script (`--sleep 5`), or run against a self-hosted
instance via `GITLAB_URL`.
