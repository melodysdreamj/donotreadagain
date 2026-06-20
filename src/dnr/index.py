"""Per-folder index (M5).

`.dnr.db` (SQLite + FTS5) harvests the records already embedded in a folder's files
into the fixed-contract `dnr` table, so an agent can query a whole folder without
opening each file. Regenerable — the truth is in the files (vision.md §11).

`index ≠ ingest`: this only *harvests* existing records (cheap, no transcription).
Incremental: stat → (changed?) → harvest; content_hash match at a new path = a move
(update path only); files gone from disk are tombstoned.

CJK note: FTS5 uses the `trigram` tokenizer so Korean/CJK substring search works
without ICU (M6).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from . import embed as _embed
from . import hashing
from .formats import SUPPORTED

DB_NAME = ".dnr.db"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".dnr", ".idea", ".vscode"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS dnr (
  content_hash TEXT PRIMARY KEY,
  path TEXT, mime TEXT, bytes INTEGER, mtime REAL, indexed_at TEXT,
  method TEXT, transcriber TEXT, version TEXT, lang TEXT,
  title TEXT, summary TEXT, tags TEXT, transcript TEXT,
  fields TEXT, extras TEXT, whole_hash TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS dnr_fts USING fts5(
  content_hash UNINDEXED, title, summary, transcript, tokenize='trigram'
);
CREATE TABLE IF NOT EXISTS _dnr_readme (k TEXT PRIMARY KEY, v TEXT);
"""

_README = {
    "about": "dnr per-folder index. Fixed table `dnr` (content_hash PRIMARY KEY) + FTS5 "
             "`dnr_fts` (trigram). Regenerable from the files. See https://github.com/.../dnr.",
    "examples": "SELECT path FROM dnr WHERE method='vision' AND lang='ko';\n"
                "SELECT d.path FROM dnr_fts JOIN dnr d ON d.content_hash=dnr_fts.content_hash "
                "WHERE dnr_fts MATCH 'damages';\n"
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


def _harvest(con, folder, abspath, rec) -> None:
    ch = rec.get("content_hash")
    st = os.stat(abspath)
    rel = os.path.relpath(abspath, folder)
    tr = rec.get("transcript") or {}
    prov = rec.get("provenance") or {}
    fields = rec.get("fields") or {}
    src = rec.get("source") or {}
    tags = fields.get("tags")
    row = (
        ch, rel, src.get("mime"), st.st_size, st.st_mtime,  # bytes = on-disk size (used by incremental stat-skip)
        datetime.now(timezone.utc).isoformat(),
        prov.get("method"), prov.get("transcriber"), prov.get("version"), tr.get("lang"),
        fields.get("title"), fields.get("summary"),
        json.dumps(tags, ensure_ascii=False) if tags is not None else None,
        tr.get("text"),
        json.dumps(fields, ensure_ascii=False), json.dumps(rec.get("extras") or {}, ensure_ascii=False),
        hashing.whole_hash(abspath),
    )
    con.execute("INSERT OR REPLACE INTO dnr VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
    con.execute("DELETE FROM dnr_fts WHERE content_hash=?", (ch,))
    con.execute(
        "INSERT INTO dnr_fts(content_hash,title,summary,transcript) VALUES (?,?,?,?)",
        (ch, fields.get("title"), fields.get("summary"), tr.get("text")),
    )


def scan(folder) -> dict:
    """Incrementally bring the folder's index up to date. Returns counts."""
    folder = str(folder)
    con = open_db(folder)
    try:
        existing = {r["path"]: r for r in con.execute("SELECT path, bytes, mtime, content_hash FROM dnr")}
        seen_paths: set[str] = set()
        seen_hashes: set[str] = set()
        indexed = skipped = moved = removed = errored = 0

        for abspath in _iter_files(folder):
            rel = os.path.relpath(abspath, folder)
            seen_paths.add(rel)
            try:
                st = os.stat(abspath)
                prev = existing.get(rel)
                if prev and prev["bytes"] == st.st_size and abs((prev["mtime"] or 0) - st.st_mtime) < 1e-6:
                    skipped += 1
                    seen_hashes.add(prev["content_hash"])
                    continue
                rec = _embed.extract(abspath)
                if rec is None:
                    continue  # no record (or unreadable) -> skip; index != ingest
                ch = rec.get("content_hash")
                hit = con.execute("SELECT path FROM dnr WHERE content_hash=?", (ch,)).fetchone()
                if hit and hit["path"] != rel:  # same content at a new path = a move
                    con.execute("UPDATE dnr SET path=?, mtime=?, bytes=? WHERE content_hash=?",
                                (rel, st.st_mtime, st.st_size, ch))
                    moved += 1
                    seen_hashes.add(ch)
                    continue
                _harvest(con, folder, abspath, rec)
                indexed += 1
                seen_hashes.add(ch)
            except Exception:
                errored += 1  # one bad file must not abort the whole scan

        for path, r in existing.items():
            if path not in seen_paths and r["content_hash"] not in seen_hashes:
                con.execute("DELETE FROM dnr WHERE content_hash=?", (r["content_hash"],))
                con.execute("DELETE FROM dnr_fts WHERE content_hash=?", (r["content_hash"],))
                removed += 1

        con.commit()
        return {"indexed": indexed, "skipped": skipped, "moved": moved,
                "removed": removed, "errored": errored}
    finally:
        con.close()


def query_match(folder, text: str) -> list[str]:
    """Full-text search; returns matching paths (trigram, CJK-friendly)."""
    con = open_db(folder)
    try:
        rows = con.execute(
            "SELECT d.path FROM dnr_fts JOIN dnr d ON d.content_hash = dnr_fts.content_hash "
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
