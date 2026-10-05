"""Healthy = a sync succeeded within 2x the interval (or ever, in one-shot mode)."""

import json
import os
import pathlib
import sys
import time

path = pathlib.Path(os.environ.get("SYNC_STATE_DIR", "/cognee-storage/sync")) / "last_success.json"
interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "0") or 0)
try:
    finished = json.loads(path.read_text())["finished_at"]
except Exception:  # noqa: BLE001
    sys.exit(1)
if interval > 0 and time.time() - finished > 2 * interval:
    sys.exit(1)
sys.exit(0)
