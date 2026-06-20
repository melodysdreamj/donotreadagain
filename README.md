# donotreadagain (dnr)

> **Read once, never again.** A spec + tool that embeds a faithful AI transcript into each expensive-to-parse file's own metadata, so AI agents stop re-parsing the same PDF / audio / video.

**Status:** early design — building fundamentals-first. Full design doc → **[vision.md](vision.md)** (Korean).

## The idea

AI agents re-OCR / re-transcribe the same file every time they read it — slow and costly in time and tokens. dnr reads a file **once**, then writes a faithful, verbatim transcript + structured metadata **into the file's own native metadata slot** (PDF → XMP, MP3 → ID3, sidecar `.dnr.json` fallback) as a signed JSON record. The file becomes self-describing: any agent that opens it reads the cached transcript instead of re-parsing. A regenerable per-folder SQLite + FTS5 index (`.dnr.db`) makes a whole folder queryable.

- **File = canonical truth** — the record travels inside the file, location-independent.
- **Index = regenerable cache** — one `.dnr.db` per folder; rebuilt from the files anytime.
- **Consumer needs no install** — reads via ambient `sqlite3` / `exiftool`; only *ingest* (transcribe + embed) runs as a tool.

## How it fits together

```
파일 (canonical 진실)                인덱스 .dnr.db (파생, 재생성가능)
┌──────────────────────────┐  harvest ┌──────────────────────────┐
│ dnr 레코드 (XMP/ID3 슬롯)  │ ───────▶ │ 고정 테이블 + FTS5         │
│  content_hash, transcript │          │ + path, whole_hash …       │
│  provenance, fields, sig  │          └──────────────────────────┘
└──────────────────────────┘                  ▲ sqlite3로 무설치 쿼리
   ▲ 비싸게 1회 전사·임베드·서명
```

## Status / roadmap

v0.1 is built fundamentals-first. The load-bearing primitive — a per-format **canonical `content_hash`** that stays invariant when the record is embedded — is validated first (the "make-or-break" experiment), then signing, embed, and the index. See [vision.md](vision.md) §16.

## License

[MIT](LICENSE) © 2026 june lee
