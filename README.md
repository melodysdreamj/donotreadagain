# donotreadagain (dnr)

> **Read once, never again.** A spec + tool that embeds a faithful AI transcript into each expensive-to-parse file's own metadata, so AI agents stop re-parsing the same PDF / audio / video.

**Status:** working v0.1 engine (PDF + audio, zero-API-key). Full design → **[vision.md](vision.md)** · spec → **[spec/dnr-0.1.md](spec/dnr-0.1.md)** · security → **[SECURITY.md](SECURITY.md)** · roadmap → **[MILESTONES.md](MILESTONES.md)**.

```
dnr ingest <file>     # transcribe once (local) → sign → embed
dnr read <file>       # print the cached transcript (verified) or fall back
dnr index <folder>    # build .dnr.db    dnr query <folder> --match "<text>"
dnr init              # install the agent skill ("apply dnr")
dnr strip <file>      # remove the record before sharing
```

## The idea

AI agents re-OCR / re-transcribe the same file every time they read it — slow and costly in time and tokens. dnr reads a file **once**, then writes a faithful, verbatim transcript + structured metadata **into the file's own native metadata slot** (PDF → XMP, MP3 → ID3, sidecar `.dnr.json` fallback) as a signed JSON record. The file becomes self-describing: any agent that opens it reads the cached transcript instead of re-parsing. A regenerable per-folder SQLite + FTS5 index (`.dnr.db`) makes a whole folder queryable.

- **File = canonical truth** — the record travels inside the file, location-independent.
- **Index = regenerable cache** — one `.dnr.db` per folder; rebuilt from the files anytime.
- **Consumer needs no install** — reads via ambient `sqlite3` / `exiftool`; only *ingest* (transcribe + embed) runs as a tool.

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
