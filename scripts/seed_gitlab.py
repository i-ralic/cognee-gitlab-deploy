"""Fill a GitLab project you own with real public text, so Part 3 can edit/add/delete.

Copies issues (title, description, labels, state) and their non-system comments from
a public source project into your target project, and opens a handful of merge
requests, each on its own branch with one commit. Idempotent-ish: skips source issues
whose title already exists in the target. Attribution: every copied item ends with a
line naming its origin URL.

  export GITLAB_TOKEN=glpat-...          # api scope on the TARGET project
  python scripts/seed_gitlab.py --source inkscape/vectors/content --target you/cognee-corpus \
      --issues 150 --merge-requests 20
"""

import argparse
import os
import sys
import time
from urllib.parse import quote

import requests

BASE = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
TOKEN = os.environ.get("GITLAB_TOKEN")
S = requests.Session()
S.headers.update({"Accept": "application/json", **({"PRIVATE-TOKEN": TOKEN} if TOKEN else {})})


def api(method, path, **kw):
    for attempt in range(5):
        r = S.request(method, f"{BASE}/api/v4{path}", timeout=60, **kw)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(float(r.headers.get("Retry-After", 2**attempt)))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()


def paginate(path, params):
    page = 1
    while True:
        r = api("GET", path, params={**params, "per_page": 100, "page": page})
        rows = r.json()
        yield from rows
        if not r.headers.get("X-Next-Page"):
            return
        page = int(r.headers["X-Next-Page"])


def proj(p):
    return quote(p, safe="")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--issues", type=int, default=150)
    ap.add_argument("--merge-requests", type=int, default=20)
    a = ap.parse_args()
    if not TOKEN:
        sys.exit("GITLAB_TOKEN with api scope is required")

    src, tgt = proj(a.source), proj(a.target)
    existing = {i["title"] for i in paginate(f"/projects/{tgt}/issues", {"state": "all"})}
    print(f"target already has {len(existing)} issues")

    copied = 0
    for issue in paginate(f"/projects/{src}/issues", {"state": "all", "order_by": "updated_at", "sort": "desc"}):
        if copied >= a.issues:
            break
        if issue["title"] in existing or not (issue.get("description") or "").strip():
            continue
        body = f"{issue['description']}\n\n---\n_Copied from {issue['web_url']} for a test corpus._"
        created = api("POST", f"/projects/{tgt}/issues", json={
            "title": issue["title"], "description": body[:60000],
            "labels": ",".join(issue.get("labels") or []),
        }).json()
        for note in paginate(f"/projects/{src}/issues/{issue['iid']}/notes", {"sort": "asc"}):
            if note.get("system") or not (note.get("body") or "").strip():
                continue
            api("POST", f"/projects/{tgt}/issues/{created['iid']}/notes",
                json={"body": f"{note['author']['username']} wrote:\n\n{note['body'][:20000]}"})
        if issue["state"] == "closed":
            api("PUT", f"/projects/{tgt}/issues/{created['iid']}", json={"state_event": "close"})
        copied += 1
        print(f"issue #{created['iid']} <- {issue['web_url']}")

    # Merge requests: one branch + one commit each, body copied from a source MR.
    made = 0
    default_branch = api("GET", f"/projects/{tgt}").json().get("default_branch") or "main"
    for mr in paginate(f"/projects/{src}/merge_requests", {"state": "all", "order_by": "updated_at", "sort": "desc"}):
        if made >= a.merge_requests:
            break
        if not (mr.get("description") or "").strip():
            continue
        branch = f"seed/mr-{mr['iid']}"
        try:
            api("POST", f"/projects/{tgt}/repository/commits", json={
                "branch": branch, "start_branch": default_branch,
                "commit_message": f"seed: {mr['title'][:60]}",
                "actions": [{"action": "create", "file_path": f"seed/mr-{mr['iid']}.md",
                             "content": f"# {mr['title']}\n\nSeeded from {mr['web_url']}\n"}],
            })
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                continue  # branch exists from a previous run
            raise
        created = api("POST", f"/projects/{tgt}/merge_requests", json={
            "source_branch": branch, "target_branch": default_branch, "title": mr["title"],
            "description": f"{mr['description']}\n\n---\n_Copied from {mr['web_url']} for a test corpus._"[:60000],
            "labels": ",".join(mr.get("labels") or []),
        }).json()
        for note in paginate(f"/projects/{src}/merge_requests/{mr['iid']}/notes", {"sort": "asc"}):
            if note.get("system") or not (note.get("body") or "").strip():
                continue
            api("POST", f"/projects/{tgt}/merge_requests/{created['iid']}/notes",
                json={"body": f"{note['author']['username']} wrote:\n\n{note['body'][:20000]}"})
        made += 1
        print(f"MR !{created['iid']} <- {mr['web_url']}")
    print(f"done: {copied} issues, {made} merge requests")


if __name__ == "__main__":
    main()
