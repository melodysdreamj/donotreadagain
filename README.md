# donotreadagain (dnr)

> **Read once, never again.** A spec + tool that embeds a faithful AI transcript into each expensive-to-parse file's own metadata, so AI agents stop re-parsing the same PDF / audio / video.

**Status:** working v0.1 engine (PDF + audio, zero-API-key). Full design → **[vision.md](vision.md)** · spec → **[spec/dnr-0.1.md](spec/dnr-0.1.md)** · security → **[SECURITY.md](SECURITY.md)** · settled design Q&A → **[qna.md](qna.md)** · roadmap → **[MILESTONES.md](MILESTONES.md)**.

```
dnr ingest <file>     # transcribe once (local) → sign → embed (--no-embed = db-only, original untouched)
dnr read <file>       # print the cached transcript (verified) or fall back
dnr index <folder>    # build .dnr.db    dnr query <folder> --match "<text>"
dnr skill             # print SKILL.md — an agent fetches it once, then knows dnr everywhere
dnr strip <file>      # remove the record before sharing
```

**Requires Python 3.10+** (which also provides the `sqlite3` used to read the index — one dependency covers both). Install with `pipx install donotreadagain` / `pip install donotreadagain`, or run without a persistent install via `uvx --from donotreadagain dnr <cmd>`. (A standalone binary for Python-less environments is future work.)

## The idea

AI agents re-OCR / re-transcribe the same file every time they read it — slow and costly in time and tokens. dnr reads a file **once**, then writes a faithful, verbatim transcript + structured metadata **into the file's own native metadata slot** (PDF → XMP, MP3 → ID3, PNG → iTXt, JPEG → APP segment) as a signed JSON record — pixels/content untouched. The file becomes self-describing: any agent that opens it reads the cached transcript instead of re-parsing. Formats with no slot but that still need transcription (docx, …) store a **db-only** record in the per-folder SQLite + FTS5 index (`.dnr.db`), which also makes a folder queryable; already-readable text (txt/md/csv) needs no record at all. **No `.dnr.json` sidecars.**

- **File = canonical truth** — the record travels inside the file, location-independent.
- **Index = regenerable cache** — one `.dnr.db` per folder; rebuilt from the files anytime.
- **Consumer needs no *persistent* install** — given Python (assumed present; its stdlib includes `sqlite3`), an agent can read the index or run `dnr` via `uvx`. A truly zero-runtime path (standalone binary) is deferred.
- **No per-folder note** — each record self-describes via an `_about` pointer (and the `.dnr.db` readme), so an agent that meets a dnr file fetches the skill (`SKILL.md`) **once** and then knows dnr in every folder. Nothing is dropped into your folders.

## How it fits together

```
File (canonical truth)                Index .dnr.db (derived, regenerable)
┌──────────────────────────┐  harvest ┌──────────────────────────┐
│ dnr record (XMP/ID3 slot) │ ───────▶ │ fixed table + FTS5         │
│  content_hash, transcript │          │ + path, whole_hash …       │
│  provenance, fields, sig  │          └──────────────────────────┘
└──────────────────────────┘                  ▲ query via sqlite3, no install
   ▲ transcribe·embed·sign once (expensive)
```

## Status / roadmap

v0.1 is built fundamentals-first. The load-bearing primitive — a per-format **canonical `content_hash`** that stays invariant when the record is embedded — was validated first (the "make-or-break" experiment, ✅ passed for PDF/audio); signing, embed, and the index follow. See [vision.md](vision.md) §16 and [MILESTONES.md](MILESTONES.md).

## License

[MIT](LICENSE) © 2026 june lee
