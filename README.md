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

_Filled in as each is measured; see REPORT.md for the corpus analysis._

- Where the sync runs
- Which databases
- Model caches
- Resource requests and limits (measured)
- Health checks
- `ENABLE_BACKEND_ACCESS_CONTROL`

## Layout

```
docker-compose.yml   postgres + api + sync (sync is a profile; never starts with `up`)
sync/Dockerfile      cognee/cognee:main + the connector, nothing else
sync/sync.py         one foreground remember(); optional loop; writes last_success.json
sync/healthcheck.py  healthy = last success within 2x the interval
scripts/ask.sh       POST /api/v1/search, CHUNKS, over the synced dataset
REPORT.md            Part 3: what ended up in the graph and what did not
```
