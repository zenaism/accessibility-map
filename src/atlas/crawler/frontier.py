"""The frontier: every URL the crawler has ever seen, with a status, on disk (SQLite).

Because it lives on disk, a crash loses at most the page in flight, a second crawl knows what it fetched before
(for conditional requests and change detection), and the completeness checks can prove that no URL was forgotten.
States: queued -> fetched | failed | skipped | blocked | unchanged. Nothing is deleted.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

from ..core import now

COLUMNS = [
    "url", "host", "state", "reason", "depth", "via", "parent", "score", "attempts", "etag", "last_modified",
    "content_sha", "status", "content_type", "bytes", "final_url", "section", "pattern", "first_seen",
    "last_fetched", "change_count", "crawl_id", "lastmod", "rendered",
]  # fmt: skip
STATES = ("queued", "fetched", "failed", "skipped", "blocked", "unchanged")


class Frontier:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS urls ("
            "url TEXT PRIMARY KEY, host TEXT, state TEXT, reason TEXT, depth INTEGER, via TEXT, parent TEXT, "
            "score REAL, attempts INTEGER DEFAULT 0, etag TEXT, last_modified TEXT, content_sha TEXT, status INTEGER, "
            "content_type TEXT, bytes INTEGER, final_url TEXT, section TEXT, pattern TEXT, first_seen TEXT, "
            "last_fetched TEXT, change_count INTEGER DEFAULT 0, crawl_id TEXT, lastmod TEXT)"
        )
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(urls)")}
        if "rendered" not in cols:  # older frontier files
            self.db.execute("ALTER TABLE urls ADD COLUMN rendered INTEGER DEFAULT 0")
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_state ON urls(state)")
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_pattern ON urls(pattern)")
        self.db.commit()

    def known(self, url: str) -> bool:
        return self.db.execute("SELECT 1 FROM urls WHERE url=?", (url,)).fetchone() is not None

    def add(self, url: str, **cols) -> bool:
        """Record a URL the first time it is seen; False if already known (a duplicate, not an error)."""
        if self.known(url):
            return False
        cols = {"state": "queued", "first_seen": now(), **cols, "url": url}
        names = ", ".join(cols)
        self.db.execute(
            f"INSERT INTO urls ({names}) VALUES ({', '.join('?' * len(cols))})", list(cols.values())
        )
        self.db.commit()
        return True

    def update(self, url: str, **cols) -> None:
        if not cols:
            return
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.execute(f"UPDATE urls SET {sets} WHERE url=?", [*cols.values(), url])
        self.db.commit()

    def get(self, url: str) -> dict | None:
        cur = self.db.execute("SELECT * FROM urls WHERE url=?", (url,))
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row, strict=True)) if row else None

    def bump_attempts(self, url: str) -> None:
        self.db.execute("UPDATE urls SET attempts=attempts+1 WHERE url=?", (url,))
        self.db.commit()

    def counts(self) -> Counter:
        return Counter(dict(self.db.execute("SELECT state, COUNT(*) FROM urls GROUP BY state").fetchall()))

    def reasons(self, state: str) -> Counter:
        rows = self.db.execute(
            "SELECT COALESCE(reason,''), COUNT(*) FROM urls WHERE state=? GROUP BY reason", (state,)
        )
        return Counter(dict(rows.fetchall()))

    def count_where(self, column: str, value) -> int:
        return self.db.execute(f"SELECT COUNT(*) FROM urls WHERE {column}=?", (value,)).fetchone()[0]

    def rows(self, state: str | None = None) -> list[dict]:
        q = "SELECT * FROM urls" + (" WHERE state=?" if state else "")
        cur = self.db.execute(q, (state,) if state else ())
        names = [c[0] for c in cur.description]
        return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]

    def close(self) -> None:
        self.db.close()
