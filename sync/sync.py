"""Run one GitLab → cognee sync in the foreground, optionally on an interval.

Foreground matters: cognee only runs forget-on-delete (orphan cleanup) when
remember() is awaited in the calling process, never for background runs.

Exit code 0 = the sync finished and the cursor advanced; non-zero = it failed and
staging/memory were left as they were. ``SYNC_INTERVAL_SECONDS > 0`` loops.
"""

import asyncio
import json
import os
import pathlib
import sys
import time

import cognee

from cognee_community_connector_gitlab import gitlab_source

DATASET = os.environ.get("COGNEE_DATASET", "gitlab_project")
INTERVAL = int(os.environ.get("SYNC_INTERVAL_SECONDS", "0") or 0)
STATE_DIR = pathlib.Path(os.environ.get("SYNC_STATE_DIR", "/cognee-storage/sync"))
# Comments need a token; allow turning them off for public read-only runs.
INCLUDE_COMMENTS = os.environ.get("GITLAB_INCLUDE_COMMENTS", "true").lower() not in ("0", "false", "no")

REMEMBER_KWARGS = {"primary_key": "id", "write_disposition": "merge", "max_rows_per_table": 0}


async def run_once() -> None:
    started = time.time()
    result = await cognee.remember(
        gitlab_source(include_comments=INCLUDE_COMMENTS), dataset_name=DATASET, **REMEMBER_KWARGS
    )
    elapsed = time.time() - started
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "last_success.json").write_text(
        json.dumps({"finished_at": time.time(), "elapsed_s": round(elapsed, 1),
                    "dataset": DATASET, "result": str(result)[:2000]})
    )
    print(f"sync ok in {elapsed:.0f}s: {result}", flush=True)


def main() -> int:
    while True:
        try:
            asyncio.run(run_once())
        except Exception as exc:  # noqa: BLE001 - report and keep the loop alive
            print(f"sync FAILED: {exc!r}", file=sys.stderr, flush=True)
            if INTERVAL <= 0:
                return 1
        if INTERVAL <= 0:
            return 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
