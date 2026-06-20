"""Per-folder index (M5).

`.dnr.db` (SQLite + FTS5) harvests records already embedded in a folder's files into
the fixed-contract `dnr` table, so an agent can query a folder without opening each
file. Regenerable — the truth is in the files (vision.md §11).

Security (fixed after multi-user dogfooding): the index is part of the trust boundary.
`scan` harvests a record ONLY if it is signed by a trusted key AND its content_hash
matches the file — the same gate as `read` (vision.md §9). Unsigned / forged / tampered
records are never indexed, so `query` cannot surface them.

Identity: each row is keyed by **path** (one row per file), so two distinct files with
identical content do not collide. A file with no valid record is not indexed (and any
stale row for it is removed); files gone from disk are tombstoned.

`index ≠ ingest`: this only harvests existing records (cheap, no transcription).
CJK: FTS5 uses the `trigram` tokenizer (substring match, 3+ chars).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from . import embed as _embed
from . import hashing, keyring, signing
from .formats import SUPPORTED

DB_NAME = ".dnr.db"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".dnr", ".idea", ".vscode"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS dnr (
  content_hash TEXT, path TEXT, mime TEXT, bytes INTEGER, mtime REAL, indexed_at TEXT,
  method TEXT, transcriber TEXT, version TEXT, lang TEXT,
  title TEXT, summary TEXT, tags TEXT, transcript TEXT,
  fields TEXT, extras TEXT, whole_hash TEXT,
  PRIMARY KEY (path)
);
CREATE VIRTUAL TABLE IF NOT EXISTS dnr_fts USING fts5(
  path UNINDEXED, title, summary, transcript, tokenize='trigram'
);
CREATE TABLE IF NOT EXISTS _dnr_readme (k TEXT PRIMARY KEY, v TEXT);
"""

_README = {
    "about": "dnr per-folder index. Fixed table `dnr` (row per file, PRIMARY KEY path) + FTS5 "
             "`dnr_fts` (trigram). Only trusted (signed + content_hash-matching) records are indexed.",
    "examples": "SELECT path FROM dnr WHERE method='vision' AND lang='ko';\n"
                "SELECT d.path FROM dnr_fts JOIN dnr d ON d.path=dnr_fts.path WHERE dnr_fts MATCH 'damages';\n"
                "SELECT path FROM dnr WHERE json_extract(fields,'$.start_date') > '2024-01-01';",
}


def db_path(folder) -> str:
    return os.path.join(str(folder), DB_NAME)


def open_db(folder) -> sqlite3.Connection:
    con = sqlite3.connect(db_path(folder))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    con.executemany("INSERT OR IGNORE INTO _dnr_readme(k, v) VALUES (?, ?)", list(_README.items()))
    con.commit()
    return con


def _iter_files(folder):
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn == DB_NAME or fn.endswith((".dnr.json", ".dnr.db-wal", ".dnr.db-shm")):
                continue
            if os.path.splitext(fn)[1].lower() in SUPPORTED:
                yield os.path.join(root, fn)


def _delete_row(con, rel: str) -> None:
    con.execute("DELETE FROM dnr WHERE path=?", (rel,))
    con.execute("DELETE FROM dnr_fts WHERE path=?", (rel,))


def _harvest(con, folder, abspath, rec, st) -> None:
    rel = os.path.relpath(abspath, folder)
    tr = rec.get("transcript") or {}
    prov = rec.get("provenance") or {}
    fields = rec.get("fields") or {}
    src = rec.get("source") or {}
    tags = fields.get("tags")
    row = (
        rec.get("content_hash"), rel, src.get("mime"), st.st_size, st.st_mtime,
        datetime.now(timezone.utc).isoformat(),
        prov.get("method"), prov.get("transcriber"), prov.get("version"), tr.get("lang"),
        fields.get("title"), fields.get("summary"),
        json.dumps(tags, ensure_ascii=False) if tags is not None else None,
        tr.get("text"),
        json.dumps(fields, ensure_ascii=False), json.dumps(rec.get("extras") or {}, ensure_ascii=False),
        hashing.whole_hash(abspath),
    )
    con.execute("INSERT OR REPLACE INTO dnr VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
    con.execute("DELETE FROM dnr_fts WHERE path=?", (rel,))
    con.execute("INSERT INTO dnr_fts(path,title,summary,transcript) VALUES (?,?,?,?)",
                (rel, fields.get("title"), fields.get("summary"), tr.get("text")))


def scan(folder, trust: dict | None = None) -> dict:
    """Incrementally bring the folder's index up to date. Only trusted records are indexed."""
    folder = str(folder)
    trust = keyring.default_trust() if trust is None else trust
    con = open_db(folder)
    try:
        existing = {r["path"]: r for r in con.execute("SELECT path, bytes, mtime FROM dnr")}
        seen_paths: set[str] = set()
        indexed = skipped = removed = errored = untrusted = 0

        for abspath in _iter_files(folder):
            rel = os.path.relpath(abspath, folder)
            seen_paths.add(rel)
            try:
                st = os.stat(abspath)
                prev = existing.get(rel)
                if prev and prev["bytes"] == st.st_size and abs((prev["mtime"] or 0) - st.st_mtime) < 1e-6:
                    skipped += 1
                    continue
                rec = _embed.extract(abspath)
                trusted = (
                    rec is not None
                    and signing.verify(rec, trust)
                    and rec.get("content_hash") == hashing.content_hash(abspath)
                )
                if not trusted:
                    if rec is not None:
                        untrusted += 1  # present but forged/unsigned/mismatched -> never indexed
                    if prev is not None:  # had a row (e.g. record was stripped) -> drop it
                        _delete_row(con, rel)
                        removed += 1
                    continue
                _harvest(con, folder, abspath, rec, st)
                indexed += 1
            except Exception:
                errored += 1  # one bad file must not abort the whole scan

        for path in list(existing):
            if path not in seen_paths:
                _delete_row(con, path)
                removed += 1

        con.commit()
        return {"indexed": indexed, "skipped": skipped, "removed": removed,
                "errored": errored, "untrusted": untrusted}
    finally:
        con.close()


def query_match(folder, text: str) -> list[str]:
    """Full-text search → matching paths.

    Uses the FTS5 trigram index for terms of 3+ chars; for shorter terms (e.g. 2-char
    CJK like 계약/이혼/특허) it falls back to a substring scan so they still match (M6).
    """
    con = open_db(folder)
    try:
        term = text.strip()
        if len(term) < 3:
            like = f"%{term}%"
            rows = con.execute(
                "SELECT path FROM dnr WHERE transcript LIKE ? OR title LIKE ? OR summary LIKE ? "
                "ORDER BY path",
                (like, like, like),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT d.path FROM dnr_fts JOIN dnr d ON d.path = dnr_fts.path "
                "WHERE dnr_fts MATCH ? ORDER BY rank",
                (text,),
            ).fetchall()
        return [r["path"] for r in rows]
    finally:
        con.close()


def query_where(folder, where: str, params: tuple = ()) -> list[dict]:
    """Structured query over the fixed columns (local tool; `where` is trusted input)."""
    con = open_db(folder)
    try:
        rows = con.execute(f"SELECT * FROM dnr WHERE {where}", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def list_all(folder) -> list[dict]:
    """Return every indexed row (the inventory)."""
    con = open_db(folder)
    try:
        return [dict(r) for r in con.execute("SELECT * FROM dnr ORDER BY path")]
    finally:
        con.close()
