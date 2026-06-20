# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased] — 0.1.0

First public cut. Pre-release.

### Added
- **Read-once cache.** `dnr ingest` / `dnr record` transcribe a file once, sign the record (Ed25519),
  and embed it in the file's own metadata; `dnr read` returns the verified transcript instead of re-parsing.
- **Per-format `content_hash`** over *decoded* content (PDF streams, audio frames, decoded pixels, OOXML
  manifest, NFC text), invariant under embedding — the identity + re-transcribe trigger.
- **In-file carriers:** PDF (XMP), MP3 (ID3), PNG (iTXt), JPEG (APP segment). Pixels/content untouched.
- **db-only records** in a per-folder `.dnr.db` for slotless formats (docx, …) and `--no-embed`
  (evidentiary originals, byte-identical). Already-readable text gets no record. **No sidecar files.**
- **Per-folder index** (SQLite + FTS5 trigram, Korean/CJK ok): `dnr index` + `dnr query` with composed
  filters (`--match` ∩ `--tag` ∩ `--since/--until` ∩ `--where`), `--any` OR sweeps, `--dedup`,
  `--min-chars`, `--context` KWIC, `--format json`.
- **Query memory:** saved queries (`--save`/`dnr queries`/`--use`, re-run live), `dnr tag` and `dnr date`
  for explicit (never-inferred) metadata.
- **Self-describing distribution:** each record carries an `_about` pointer, the `.dnr.db` self-describes,
  and agents fetch the skill once (`dnr skill` / `SKILL.md`). `dnr init` just ensures a key.
- **Trust + quality:** signature + content_hash gate on `read`/`index`/`verify`; a low-quality
  (empty/mojibake) transcript heuristic flagged by `dnr status` (`trusted ≠ faithful`).
- CLI: `keygen, ingest, record, read, verify, guide, types, status, date, index, query, queries, tag,
  init, skill, strip, validate, schema`.
- Spec (`spec/dnr-0.1.md`) + JSON Schema + golden vectors; threat model (`SECURITY.md`).

### Known limits
- Not yet on PyPI; a standalone binary (Python-less environments) is future work.
- Adoption (agents *knowing* dnr) is the real lever, not the tool alone.
- More in-file carriers (OOXML, audio containers, video) and pre-query auto-scan are planned.
