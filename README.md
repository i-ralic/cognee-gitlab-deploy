# cognee + GitLab connector, running without an LLM key

Runs [cognee](https://github.com/topoteretes/cognee) and the
[GitLab connector](https://github.com/i-ralic/cognee-community/pull/1) in containers with no LLM
API key: the graph is extracted by cognee's local GLiNER model and embeddings come from a local
fastembed model. One Postgres holds all three stores. A second container runs the sync.

## Three commands

```bash
cp .env.example .env            # set GITLAB_PROJECT (and GITLAB_TOKEN for comments)
docker compose up -d            # 1. bring the stack up: postgres + api
docker compose run --rm sync    # 2. run a sync (re-run any time; second run is incremental)
./scripts/ask.sh "Which issues mention a crash on startup?"   # 3. ask a question
```

Scheduled syncs: `SYNC_INTERVAL_SECONDS=3600 docker compose --profile sync up -d sync` keeps one
sync container looping; or put `docker compose run --rm sync` in cron. Both see the same data
because both talk to the same Postgres.

## Decisions (the reasoning the task asks for)

**Where the sync runs: a second container on the same image.** `remember()` with a dlt source
runs in the process that calls it; it is not an HTTP call. The API process could do both, but a
GLiNER extraction over a hundred documents is minutes of CPU, and the published image does not
contain the connector. So `sync` is `cognee/cognee:main` plus one `pip install --no-deps` of the
connector, with its own entrypoint, its own memory limit and its own failure domain. It runs once
per `docker compose run --rm sync`, or loops with `SYNC_INTERVAL_SECONDS`. It always runs
`remember()` in the foreground, because cognee only runs forget-on-delete (orphan cleanup) for
foreground syncs. Both containers see the same data because both talk to the same Postgres.

**Which databases: one Postgres for all three stores.** cognee's defaults (SQLite, LanceDB,
Ladybug) are embedded, file-based, single-process stores; cognee itself serialises dlt staging
behind a lock *inside one process* and says nothing about two processes. Two containers writing
the same embedded files is undefined behaviour, so the choice is really "one process" versus
"a database server". Postgres carries relational (`DB_PROVIDER=postgres`), vectors
(`VECTOR_DB_PROVIDER=pgvector`) and the graph (`GRAPH_DATABASE_PROVIDER=postgres_demo`) in one
service that the `pgvector/pgvector:pg17` image provides. The dlt destination follows the
relational provider, so the connector's cursor and known-id set also land in Postgres
(`_dlt_pipeline_state`) and survive a recreated sync container. Cost: `postgres_demo` is a demo
backend and does not support raw Cypher, so `SearchType.CYPHER` is unavailable; the report
reads the two graph tables (`graph_node`, `graph_edge`) with SQL instead. A graph-native store
(Neo4j, also in cognee's compose) is the alternative when Cypher matters more than one less
container.

**Model caches: one named volume, mounted in both containers.** `HF_HOME` and
`FASTEMBED_CACHE_PATH` point under `/cognee-storage/models`, on the `cognee_storage` volume the
image already owns as uid 1000 (a fresh volume at a custom path would be root-owned). The
~750 MB GLiNER model and the fastembed model download once, on the first sync, and the API
reuses the same fastembed cache for query embeddings.

**Resources: measured with `scripts/measure.sh`, not guessed.** First sync of 134 documents
(117 issues + 17 merge requests, public project `inkscape/vectors/content`, comments off, VM with
4 CPUs / 8 GB, Apple M-series): wall clock 287 s, of which 282 s inside `remember()`; the sync
container peaked at **3.5 GiB RSS and 3.9 cores**, the API at 634 MiB (idle), Postgres at 136 MiB.
Second sync (no changes): 13 s, sync peak 599 MiB, 0.7 cores. The GLiNER model is the memory: it
loads once per sync process (6.4 s from the cache) and runs one batched pass per chunk batch at
roughly 2 s per document on CPU. Limits in `docker-compose.yml`: sync 5 GiB (peak + ~40 %), API
1 GiB, Postgres 1 GiB; CPU is left unlimited because the sync is embarrassingly parallel across
cores and nothing else competes with it. A GPU would move the sync to seconds; nothing in the
compose file assumes one.

**Memory scales with chunks per GLiNER call, not with corpus size.** The second corpus (the
board's seeded project, 19 issues + 5 merge requests, **comments on**, documents up to 33 KB /
5,200 words) OOM-killed the 5 GiB sync container three times at cognee's defaults. Measured
inside the image: the process sits at **2.7 GiB** once cognee, torch and GLiNER are loaded;
scoring one 384-word window adds nothing visible; four windows in one pass add ~1 GiB; a
14-window document in one pass passes 5 GiB and dies. cognee hands GLiNER every chunk of a
document in one call (`chunks_per_batch` defaults to 2000) and GLiNER scores 16 of them per
forward pass, so the limit was never about the number of documents. `sync.py` therefore passes
`chunks_per_batch` (`SYNC_CHUNKS_PER_BATCH`, default 4) and `data_per_batch`
(`SYNC_DATA_PER_BATCH`, default 4) to `remember()`. With both at 4 the 24-document sync took
125 s and peaked at **4.5 GiB**; the 2-changed/1-deleted re-sync took 15 s and peaked at 3.0 GiB.
On a host with less than 8 GB for the VM, set `SYNC_DATA_PER_BATCH=2`.

**Closed schema from an ontology file, not the label-bank probe.** Without a schema cognee
builds one per document by running the whole 30-label bank over a 3,000-word "sketch" of the
document in a single unwindowed pass; on long issue threads that pass alone needs > 5 GiB (it
was the first OOM). `ontology/gitlab.owl` names 9 entity types and 8 relation types that fit a
software project's issue tracker (person, organization, software, version, event, location,
date, feature, publication; sponsors, hosts, released_on, works_on, held_in, member_of, writes,
part_of). `ONTOLOGY_FILE_PATH` points the sync container at it, the probe is skipped and
extraction runs windowed at 384 words. Side effect, visible in the report's appendix: the two
relation types the first corpus lacked (`sponsors`, `released_on`) now exist. Unset the variable
to go back to the open label bank.

**Health checks.** API: the image's own `curl -f /health`. Postgres: `pg_isready`, and both
cognee containers wait for it. Sync: "healthy" means *the last sync finished and the cursor
advanced*. One-shot mode: exit code 0 and a `last_success.json` written by `sync.py`. Loop mode:
`healthcheck.py` fails when the last success is older than twice the interval. A sync that
failed leaves staging and memory exactly as they were, which is the safe failure.

**`ENABLE_BACKEND_ACCESS_CONTROL=false`.** On, every API call needs a user token and datasets
are isolated per user, so the sync process and the API would have to authenticate as the same
user for recall to see the synced dataset, and the demo graph backend's per-user isolation is
not something this task should lean on. Off, there is one tenant, one dataset, and "both see
the same data" holds by construction. Turning it on would add: a service user for the sync,
token handling in `ask.sh`, and per-dataset databases in Postgres.

## Reproduce the appendix offline (no GitLab account)

gitlab.com blocked the account that owned the seeded project (REPORT.md, "Reproducibility
caveat"), so the edit / add / delete re-sync is also reproducible against a stand-in: a 230-line
stdlib HTTP server that serves `fixtures/offline-corpus.json` as GitLab API v4 (listing with
`state`/`order_by`/`sort`, 100 per page, `Link: rel="next"`, `X-Total`, per-item notes). The
connector only sees a different `GITLAB_URL`; nothing in it knows about the fake. The fixture is
19 public issues + 5 merge requests from `inkscape/vectors/content`, captured anonymously (so no
comments: gitlab.com needs a token for notes), 31 KB of text.

```bash
docker compose --profile offline up -d fake-gitlab
export GITLAB_URL=http://fake-gitlab:8080 GITLAB_PROJECT=1 COGNEE_DATASET=gitlab_offline GITLAB_TOKEN=
docker compose run --rm sync                                       # sync 1: 19 + 5 changed
python3 scripts/fake_gitlab.py mutate --corpus fixtures/offline-corpus.json   # edit / add / delete, with marker sentences
docker compose run --rm sync                                       # sync 2: "Issue: 2 changed, 1 deleted"
docker compose run --rm sync                                       # sync 3: 0 changed, 0 deleted
docker compose exec -T postgres psql -U cognee -d cognee_db -v ds=<dataset_id from the sync output> -f - < scripts/graph_report_dataset.sql
```

Measured on 05.10 on this stack (lima VM, 4 CPUs / 8 GB): sync 1 41 s, peak 2.8 GiB, 353 nodes /
991 edges in the dataset; sync 2 12 s, "Deleting 2 orphaned dlt row(s)", 316 / 887, the deleted
issue's chunks gone, both markers present as entities with relations; sync 3 3 s, unchanged. Full
numbers in REPORT.md → Appendix → "Re-verified offline". `git checkout fixtures/` restores the
fixture after a mutate. To refresh it: `python3 scripts/fake_gitlab.py capture --source
inkscape/vectors/content --out fixtures/offline-corpus.json`.

## Layout

```
docker-compose.yml       postgres + api + sync + fake-gitlab (sync and fake-gitlab are profiles; never start with `up`)
sync/Dockerfile          cognee/cognee:main + the connector, nothing else
sync/sync.py             one foreground remember(); batch knobs; optional loop; last_success.json
sync/healthcheck.py      healthy = last success within 2x the interval
ontology/gitlab.owl      closed GLiNER schema (9 entity types, 8 relation types) - see Decisions
scripts/ask.sh           POST /api/v1/search, CHUNKS, over the synced dataset
scripts/measure.sh       docker stats sampler: peak memory / CPU per container while a sync runs
scripts/graph_report.sql node/edge type counts, hubs, sampled relations from graph_node/graph_edge
scripts/seed_gitlab.py   copy public issues/MRs into a project you own, with attribution
scripts/mutate_corpus.py one edit, one add, one delete, each with a searchable marker sentence
scripts/fake_gitlab.py   GitLab API v4 stand-in (capture / serve / mutate) for the offline reproduction
scripts/graph_report_dataset.sql  the same counts scoped to one dataset id (graph_node.source_dataset_ids)
fixtures/offline-corpus.json      19 public issues + 5 MRs for the stand-in (see "Reproduce the appendix offline")
REPORT.md                Part 3: what ended up in the graph and what did not (+ appendix)
```
