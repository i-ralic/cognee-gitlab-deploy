# Appendix to REPORT.md: corpus, method, the edit / add / delete re-sync, reproducibility, resources

Everything here was measured on 05.10.2026 on the stack described in the README; every number traces to `scripts/graph_report.sql` / `graph_report_dataset.sql` output, the sync logs, or `scripts/measure.sh` samples.

## A. Corpus and method

- **Source:** the public GitLab project `inkscape/vectors/content` (the Inkscape marketing team's
  content tracker): **117 issues + 17 merge requests = 134 documents**, comments off (the notes
  endpoint needs a token on gitlab.com; the board's own project will add them). Real text, written
  by real people, about releases, hackfests, sponsors, articles and videos.
- **Sync 1:** 134 documents in 282 s. **Sync 2 (no changes upstream):** 0 changed, 0 deleted, 9 s,
  graph identical; the cursor and id set were restored in a fresh container from dlt state in
  Postgres (`dlt_database_gitlab_project.gitlab_project._dlt_pipeline_state`).
- **Extraction:** cognee 1.6.2 GLiNER demo (`fastino/gliner2.5-base-v1`), built-in label bank (the
  "open" bank, 30 labels) filtered per document; the seeded run used the closed `ontology/gitlab.owl`; embeddings `BAAI/bge-small-en-v1.5` via fastembed; no LLM key anywhere.
- **Counting:** `scripts/graph_report.sql` against the `postgres_demo` tables `graph_node` /
  `graph_edge`. **"Answered"** means the fact is readable in the top-5 chunks `recall()` returns;
  without an LLM there is no generated answer to grade.
- **Not available here:** `GlinerRunStats` (candidate vs kept vs dropped edges) only exists when
  the GLiNER tasks are run through `run_custom_pipeline`; `remember()` does not expose it. I did not
  spend the budget wiring a second pipeline for one counter.

Timing labels, because the README and the report quote different numbers for the same runs: **wall clock** is `measure.sh` around `docker compose run --rm sync` (container start, model load, `remember()`, teardown); **inside `remember()`** is what `sync.py` prints. First sync: 287 s wall clock, 282 s inside `remember()`. No-change sync: 13 s wall clock, 9 s inside `remember()`. Peaks are `docker stats` sampled every 5 s, so a shorter spike than that is under-read; they are lower bounds.

## B. The second sync with an edit, an add and a delete (seeded project, gitlab.com)

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

## C. Reproducibility caveat

 A few hours after the seed and mutate runs, gitlab.com blocked the
account that owns `collabwriting-app/cognee-corpus` (every authenticated call returns
`403 Your account has been blocked`), and the project's issues and merge requests now list as
empty for anonymous readers, although the project page itself still resolves. The seed script
created 19 issues, 5 branches, 5 merge requests and their comments within minutes on a fresh
account, which is the pattern GitLab's anti-abuse checks look for `[unverified: GitLab does not
state the reason]`. The main corpus (`inkscape/vectors/content`, sections 1 to 6) is a public
project and reproduces as described. To re-run this appendix, seed a project under an
established account and pace the seed script (`--sleep 5`), or run against a self-hosted
instance via `GITLAB_URL`.

## D. Re-verified offline (05.10, after the block)

 Because the seeded project can no longer be
read, the same three-sync sequence was re-run against `scripts/fake_gitlab.py`, a stand-in that
serves `fixtures/offline-corpus.json` as GitLab API v4 inside the compose network (README,
"Reproduce the appendix offline"). Same connector image, same stack, dataset `gitlab_offline`,
24 documents (19 issues + 5 merge requests from the public project, no comments). Counts are
scoped to the dataset via `graph_node.source_dataset_ids` (`scripts/graph_report_dataset.sql`).

| | Sync 1 (fresh) | `fake_gitlab.py mutate` | Sync 2 | Sync 3 |
|---|---|---|---|---|
| Connector log | 19 + 5 changed, 0 deleted | edit #39, add #120, delete #119 | **Issue: 2 changed, 1 deleted** | 0 changed, 0 deleted |
| cognee | | | "Deleting 2 orphaned dlt row(s)" | |
| Wall / sync peak RSS | 41 s / 2.8 GiB | | 12 s / 0.8 GiB | 3 s / 0.15 GiB |
| Staging rows (issues / MRs) | 19 / 5 | | 19 / 5; id of #119 gone, id of #120 present | 19 / 5 |
| TextDocument / DocumentChunk | 24 / 31 | | 24 / 29 | 24 / 29 |
| Entity | 258 | | 225 | 225 |
| Nodes / edges (dataset-scoped) | 353 / 991 | | **316 / 887** | 316 / 887 |
| Entity-entity relations | 211 | | 192 | 192 |

What the graph did, same as on gitlab.com: the deleted issue's chunks in this dataset: **0**;
the add marker produced `quokka palette is_a feature`, `mira kovac is_a person`; the edit marker
produced `collabwriting hosts zagreb hackfest 2026`, `zagreb hackfest 2026 held_in lauba hall`,
`lauba hall is_a location`, plus the same over-read `collabwriting sponsors zagreb hackfest 2026`.
`recall()` with `datasets=["gitlab_offline"]`: the Quokka sentence ranks 2 (rank 1 is the
*other* dataset's copy from the gitlab.com run, so the "search ignores the datasets filter with
access control off" finding reproduces); "Where is the Zagreb Hackfest 2026 held?" is again not in
the top 5; the deleted issue's title still returns copies from the two earlier datasets, none from
this one. The sync 2 peak (0.8 GiB vs 3.0 GiB on gitlab.com) is lower because the two changed
documents here are short and have no comments, so GLiNER scores a handful of chunks.


## E. Resources, as measured

| Run | Documents | Wall clock / inside `remember()` | Sync peak RSS / CPU | API / Postgres peak |
|---|---|---|---|---|
| Sync 1, public project, comments off | 134 | 287 s / 282 s | 3.5 GiB / 3.9 cores | 634 MiB (idle) / 136 MiB |
| Sync 2, no change | 134 | 13 s / 9 s | 599 MiB / 0.7 cores | |
| Seeded project, comments on, closed schema | 24 | 125 s | 4.5 GiB | |
| Seeded project, re-sync after edit/add/delete | 2 changed, 1 deleted | 15 s | 3.0 GiB | |
| Offline stand-in, sync 1 / 2 / 3 | 24 / 2+1 / 0 | 41 s / 12 s / 3 s | 2.8 GiB / 0.8 GiB / 0.15 GiB | |

Limits in `docker-compose.yml` follow from these: sync 5 GiB limit (4.5 GiB measured peak + ~10 %) with a 3 GiB reservation (the 2.7 GiB model baseline + one batch) and 4 CPUs; API 1 GiB; Postgres 1 GiB. The API under one `ask.sh` query is measured in README "Resources".
