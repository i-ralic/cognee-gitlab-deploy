"""Healthy = a sync of THIS dataset succeeded within 2x the interval (or ever, in one-shot mode).

The success file is keyed by dataset so two sync containers sharing one volume (two
projects) cannot satisfy each other's healthcheck.
"""

import json
import os
import pathlib
import sys
import time

dataset = os.environ.get("COGNEE_DATASET", "gitlab_project")
path = pathlib.Path(os.environ.get("SYNC_STATE_DIR", "/cognee-storage/sync")) / f"last_success.{dataset}.json"
interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "0") or 0)
try:
    record = json.loads(path.read_text())
    finished = record["finished_at"]
    if record.get("dataset") != dataset:
        sys.exit(1)
except Exception:  # noqa: BLE001
    sys.exit(1)
if interval > 0 and time.time() - finished > 2 * interval:
    sys.exit(1)
sys.exit(0)
