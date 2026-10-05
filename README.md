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

## Layout

```
docker-compose.yml   postgres + api + sync (sync is a profile; never starts with `up`)
sync/Dockerfile      cognee/cognee:main + the connector, nothing else
sync/sync.py         one foreground remember(); optional loop; writes last_success.json
sync/healthcheck.py  healthy = last success within 2x the interval
scripts/ask.sh       POST /api/v1/search, CHUNKS, over the synced dataset
REPORT.md            Part 3: what ended up in the graph and what did not
```
