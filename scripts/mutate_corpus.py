"""Make exactly one edit, one add and one delete in the seeded GitLab project.

This is the "change the source, re-sync, look at the graph" step of Part 3. Each change
carries a marker sentence nobody would write by accident, so a CHUNKS search afterwards
proves whether the change reached cognee (edit and add should hit, delete should not).

  export GITLAB_TOKEN=glpat-...   GITLAB_PROJECT=you/cognee-corpus
  python scripts/mutate_corpus.py            # picks targets itself, prints what it did
  python scripts/mutate_corpus.py --edit 12 --delete 7   # or name the issue iids
"""

import argparse
import os
import sys
import time
from urllib.parse import quote

import requests

BASE = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
TOKEN = os.environ.get("GITLAB_TOKEN")
PROJECT = os.environ.get("GITLAB_PROJECT")
S = requests.Session()
S.headers.update({"Accept": "application/json", "PRIVATE-TOKEN": TOKEN or ""})

STAMP = time.strftime("%Y%m%d-%H%M")
EDIT_MARKER = f"Marker {STAMP}: the Zagreb Hackfest 2026 is hosted by Collabwriting at the Lauba hall."
ADD_MARKER = f"Marker {STAMP}: the Quokka palette ships with Inkscape 1.5 and was drawn by Mira Kovac."


def api(method, path, **kw):
    r = S.request(method, f"{BASE}/api/v4{path}", timeout=60, **kw)
    r.raise_for_status()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edit", type=int, help="issue iid to edit (default: oldest open issue)")
    ap.add_argument("--delete", type=int, help="issue iid to delete (default: newest closed issue)")
    a = ap.parse_args()
    if not (TOKEN and PROJECT):
        sys.exit("GITLAB_TOKEN (api scope) and GITLAB_PROJECT are required")
    p = quote(PROJECT, safe="")

    issues = api("GET", f"/projects/{p}/issues", params={"state": "all", "per_page": 100, "order_by": "created_at", "sort": "asc"}).json()
    edit = next((i for i in issues if i["iid"] == a.edit), None) if a.edit else next((i for i in issues if i["state"] == "opened"), None)
    delete = next((i for i in issues if i["iid"] == a.delete), None) if a.delete else next((i for i in reversed(issues) if i["state"] == "closed" and i is not edit), None)
    if not edit or not delete or edit["iid"] == delete["iid"]:
        sys.exit("could not pick distinct edit/delete targets; pass --edit/--delete")

    # 1. EDIT: append the marker to an existing issue's description (updated_at moves → connector re-fetches it)
    api("PUT", f"/projects/{p}/issues/{edit['iid']}", json={"description": f"{edit['description'] or ''}\n\n{EDIT_MARKER}"})
    # 2. ADD: a brand-new issue
    added = api("POST", f"/projects/{p}/issues", json={"title": f"Quokka palette for Inkscape 1.5 ({STAMP})", "description": ADD_MARKER}).json()
    # 3. DELETE: remove an issue outright (not close — closed is not deleted for the connector)
    deleted_title, deleted_id = delete["title"], delete["id"]
    api("DELETE", f"/projects/{p}/issues/{delete['iid']}")

    print(f"EDITED  issue #{edit['iid']} (id {edit['id']}): {edit['web_url']}\n  marker: {EDIT_MARKER}")
    print(f"ADDED   issue #{added['iid']} (id {added['id']}): {added['web_url']}\n  marker: {ADD_MARKER}")
    print(f"DELETED issue #{delete['iid']} (id {deleted_id}): \"{deleted_title}\"")
    print("\nNow: docker compose run --rm sync   # expect: N changed (>=2), 1 deleted")


if __name__ == "__main__":
    main()
