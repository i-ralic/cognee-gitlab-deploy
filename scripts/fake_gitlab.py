"""A tiny GitLab REST API v4 stand-in, so the sync can be verified with no gitlab.com account.

Why this exists: gitlab.com blocked the fresh account that owned the seeded project (see
REPORT.md, "Reproducibility caveat"), so the edit / add / delete re-sync cannot be re-run
there. The connector's base URL is configurable (``GITLAB_URL``), so this script serves the
four endpoints the connector uses from a JSON file, inside the compose network. Edit the
file between syncs and the next sync sees the change, exactly as it would on gitlab.com.

Three modes, standard library only (it runs in ``python:3.12-slim`` with nothing installed):

  capture   copy a few public issues / merge requests from gitlab.com into a corpus file
            (anonymous: comments need a token on gitlab.com, so ``notes`` stay empty)
  serve     answer GET /api/v4/projects/<any>/{issues,merge_requests}[/<iid>/notes]
            with ``state``/``order_by``/``sort``/``updated_after`` honoured, ``per_page`` capped
            by ``--per-page-max`` (gitlab.com: 100), ``Link: rel="next"`` and ``X-Total`` headers
            like gitlab.com; the file is re-read on every request. Not covered: notes need no
            token here (gitlab.com needs one), no 429 is ever served, and the token is not checked.
  mutate    one edit, one add, one delete in the corpus file, each with a marker sentence
            (same markers as scripts/mutate_corpus.py, so the report's recall checks apply)

  python scripts/fake_gitlab.py capture --source inkscape/vectors/content --out fixtures/offline-corpus.json
  docker compose --profile offline up -d fake-gitlab        # FAKE_GITLAB_PER_PAGE_MAX=10 by default
  GITLAB_URL=http://fake-gitlab:8080 GITLAB_PROJECT=1 COGNEE_DATASET=gitlab_offline docker compose run --rm sync
  python scripts/fake_gitlab.py mutate --corpus fixtures/offline-corpus.json
  GITLAB_URL=http://fake-gitlab:8080 GITLAB_PROJECT=1 COGNEE_DATASET=gitlab_offline docker compose run --rm sync
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PER_PAGE_MAX = 100
ITEM_FIELDS = (
    "id", "iid", "title", "state", "description", "labels", "author", "created_at",
    "updated_at", "web_url", "source_branch", "target_branch",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def _load(path: str) -> dict:
    return json.loads(pathlib.Path(path).read_text())


def _save(path: str, corpus: dict) -> None:
    pathlib.Path(path).write_text(json.dumps(corpus, indent=1, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# capture: public items from gitlab.com → corpus file
# ---------------------------------------------------------------------------
def _get_json(url: str, token: str | None):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        req.add_header("PRIVATE-TOKEN", token)
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host
        return json.loads(resp.read().decode())


def capture(a: argparse.Namespace) -> int:
    base = a.gitlab_url.rstrip("/")
    proj = urllib.parse.quote(a.source, safe="")
    token = os.environ.get("GITLAB_TOKEN")
    corpus = {"source": a.source, "captured_at": _now(), "issues": [], "merge_requests": []}
    for kind, n in (("issues", a.issues), ("merge_requests", a.merge_requests)):
        url = f"{base}/api/v4/projects/{proj}/{kind}?state=all&order_by=updated_at&sort=desc&per_page={min(n, 100)}"
        for item in _get_json(url, token)[:n]:
            row = {k: item.get(k) for k in ITEM_FIELDS}
            row["author"] = {"username": (item.get("author") or {}).get("username", "")}
            row["notes"] = []
            if token:  # notes need a token on gitlab.com; anonymous capture keeps them empty
                notes = _get_json(f"{base}/api/v4/projects/{proj}/{kind}/{item['iid']}/notes?per_page=100", token)
                row["notes"] = [
                    {"body": x.get("body", ""), "system": bool(x.get("system")),
                     "author": {"username": (x.get("author") or {}).get("username", "")}}
                    for x in notes
                ]
            corpus[kind].append(row)
    _save(a.out, corpus)
    print(f"captured {len(corpus['issues'])} issues + {len(corpus['merge_requests'])} merge requests "
          f"from {a.source} → {a.out} (comments: {'yes' if token else 'none, anonymous'})")
    return 0


# ---------------------------------------------------------------------------
# serve: the four endpoints the connector calls
# ---------------------------------------------------------------------------
_ITEM_RE = re.compile(r"^/api/v4/projects/[^/]+/(issues|merge_requests)/?$")
_NOTES_RE = re.compile(r"^/api/v4/projects/[^/]+/(issues|merge_requests)/(\d+)/notes/?$")


class Handler(BaseHTTPRequestHandler):
    per_page_max = PER_PAGE_MAX
    corpus_path = "corpus.json"

    def log_message(self, fmt, *args):  # one line per request, to stdout
        sys.stdout.write("%s %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _json(self, status: int, payload, headers: dict | None = None) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server API
        url = urllib.parse.urlsplit(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        corpus = _load(self.corpus_path)

        m = _NOTES_RE.match(url.path)
        if m:
            kind, iid = m.group(1), int(m.group(2))
            item = next((x for x in corpus.get(kind, []) if int(x["iid"]) == iid), None)
            if item is None:
                return self._json(404, {"message": "404 Not found"})
            return self._json(200, item.get("notes", []))

        m = _ITEM_RE.match(url.path)
        if not m:
            return self._json(404, {"message": "404 Not found"})
        kind = m.group(1)
        rows = [{k: x.get(k) for k in ITEM_FIELDS} for x in corpus.get(kind, [])]
        # GitLab's default for issues/MRs is every state; the connector asks for state=all anyway.
        state = q.get("state", "all")
        if state != "all":
            rows = [r for r in rows if r.get("state") == state]
        updated_after = q.get("updated_after")
        if updated_after:
            rows = [r for r in rows if (r.get("updated_at") or "") > updated_after]
        key = q.get("order_by", "created_at")
        rows.sort(key=lambda r: r.get(key) or "", reverse=q.get("sort", "desc") == "desc")
        per_page = max(1, min(int(q.get("per_page", 20)), Handler.per_page_max))
        page = max(1, int(q.get("page", 1)))
        chunk = rows[(page - 1) * per_page : page * per_page]
        headers = {"X-Total": str(len(rows)), "X-Page": str(page), "X-Per-Page": str(per_page)}
        if page * per_page < len(rows):
            nxt = dict(q, page=str(page + 1), per_page=str(per_page))
            host = self.headers.get("Host", "localhost")
            headers["Link"] = f'<http://{host}{url.path}?{urllib.parse.urlencode(nxt)}>; rel="next"'
            headers["X-Next-Page"] = str(page + 1)
        return self._json(200, chunk, headers)


def serve(a: argparse.Namespace) -> int:
    Handler.corpus_path = a.corpus
    Handler.per_page_max = a.per_page_max
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"fake GitLab serving {a.corpus} on http://{a.host}:{a.port}/api/v4/ (re-read per request)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------------------
# mutate: one edit, one add, one delete
# ---------------------------------------------------------------------------
def mutate(a: argparse.Namespace) -> int:
    corpus = _load(a.corpus)
    issues = corpus["issues"]
    stamp = time.strftime("%Y%m%d-%H%M")
    edit_marker = f"Marker {stamp}: the Zagreb Hackfest 2026 is hosted by Collabwriting at the Lauba hall."
    add_marker = f"Marker {stamp}: the Quokka palette ships with Inkscape 1.5 and was drawn by Mira Kovac."

    by_created = sorted(issues, key=lambda x: x.get("created_at") or "")
    edit = next((x for x in by_created if x["iid"] == a.edit), None) if a.edit else next(
        (x for x in by_created if x.get("state") == "opened"), by_created[0])
    delete = next((x for x in by_created if x["iid"] == a.delete), None) if a.delete else next(
        (x for x in reversed(by_created) if x is not edit), None)
    if edit is None or delete is None or edit is delete:
        sys.exit("could not pick distinct edit/delete targets; pass --edit/--delete")

    now = _now()
    # 1. EDIT: append the marker; updated_at moves, so the connector re-fetches it.
    edit["description"] = f"{edit.get('description') or ''}\n\n{edit_marker}"
    edit["updated_at"] = now
    # 2. ADD: a new issue with a fresh global id and iid.
    new_id = max(int(x["id"]) for x in issues + corpus.get("merge_requests", [])) + 1
    new_iid = max(int(x["iid"]) for x in issues) + 1
    added = {
        "id": new_id, "iid": new_iid, "title": f"Quokka palette for Inkscape 1.5 ({stamp})",
        "state": "opened", "description": add_marker, "labels": [], "author": {"username": "fixture"},
        "created_at": now, "updated_at": now, "web_url": f"http://fake-gitlab/{new_iid}",
        "source_branch": None, "target_branch": None, "notes": [],
    }
    issues.append(added)
    # 3. DELETE: remove outright (closing is not deletion for the connector).
    issues.remove(delete)
    _save(a.corpus, corpus)
    print(f"EDITED  issue #{edit['iid']} (id {edit['id']}): {edit['title']}\n  marker: {edit_marker}")
    print(f"ADDED   issue #{added['iid']} (id {added['id']}): {added['title']}\n  marker: {add_marker}")
    print(f"DELETED issue #{delete['iid']} (id {delete['id']}): {delete['title']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--source", required=True, help="public project path, e.g. inkscape/vectors/content")
    c.add_argument("--issues", type=int, default=19)
    c.add_argument("--merge-requests", type=int, default=5)
    c.add_argument("--gitlab-url", default=os.environ.get("GITLAB_URL", "https://gitlab.com"))
    c.add_argument("--out", required=True)
    c.set_defaults(fn=capture)
    s = sub.add_parser("serve")
    s.add_argument("--corpus", required=True)
    s.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container-internal
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--per-page-max", type=int, default=PER_PAGE_MAX,
                   help="server-side cap on per_page (gitlab.com: 100); use 10 so a small fixture paginates")
    s.set_defaults(fn=serve)
    m = sub.add_parser("mutate")
    m.add_argument("--corpus", required=True)
    m.add_argument("--edit", type=int, help="issue iid to edit (default: oldest open issue)")
    m.add_argument("--delete", type=int, help="issue iid to delete (default: newest issue)")
    m.set_defaults(fn=mutate)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
