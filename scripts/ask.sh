#!/usr/bin/env sh
# Ask the running API a question over the synced dataset. Without an LLM key cognee
# returns matching text chunks, not a generated answer.
set -eu
Q="${1:?usage: ask.sh \"question\"}"
DATASET="${COGNEE_DATASET:-gitlab_project}"
curl -sS -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d "{\"searchType\": \"CHUNKS\", \"query\": $(printf '%s' "$Q" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'), \"datasets\": [\"$DATASET\"], \"topK\": 5}"
echo
