# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## Unreleased

### Changed
- Default all new records to db-only `.dnr.db` storage so original files stay byte-identical; in-file
  metadata records now require explicit `--embed`.
- Remove the global agent bootstrap path from the CLI and agent skill; dnr is now scoped to the
  current project/task unless an agent file is explicitly updated.
- Make the dnr-first agent habit explicit in README, SKILL, `dnr init`, and local agent bootstrap
  text so agents know to read cached transcripts first, cache expensive misses, and avoid bulk
  transcription unless asked.
- Add `HARNESS.md` plus Python, TypeScript, and agent-instruction examples for read-through
  transcript cache integrations.
- Add `PROTOCOL.md` to position dnr as the reference implementation of a portable verified
  transcript-record protocol.

## 0.2.2 - 2026-06-21

### Fixed
- Force CLI stdout/stderr to UTF-8 so transcripts and Korean output survive Windows legacy code pages.

## 0.2.1 - 2026-06-21

### Fixed
- Add MP4-family content hashing and in-file carriers for M4A/MP4/MOV records, so M4A audio
  no longer advertises local ingest while failing before record creation.
- Add content hashes and in-file comment carriers for FLAC/OGG/OPUS.
- Add HEIC/HEIF db-only vision-record support via an optional pillow-heif decoded-pixel hash.

## 0.2.0 - 2026-06-21

### Changed
- Prefer PyMuPDF for PDF text extraction with pypdf fallback for better Korean/CJK results.
- Add local XLSX extraction via openpyxl.
- Add folder backfill via `dnr backfill <folder>` and `dnr ingest <folder>`, processing local-provider
  files while listing agent/vision gaps.
- Make status coverage honest by separating usable cached transcripts from low-quality records that
  need repair; add `dnr status --format json`.
- Add SQLite `busy_timeout`, reduce read-path DB writes, support `--context` with composed queries,
  and add `--any-tag` for OR tag queries.
- Clarify installation wording around `pipx install donotreadagain` as the recommended path,
  `uvx` as the one-off fallback, and audio ASR as an optional faster-whisper/ffmpeg setup.
- Reframe dnr as the cache/trust/index layer for transcripts produced by local extractors, local ASR,
  APIs, or the calling agent.

## 0.1.8

### Changed
- Agent instructions now distinguish active-read quality repair from bulk OCR: if a file is needed
  and its cached transcript is empty/garbled/unusable, agents should repair that file without asking,
  but still ask before expanding to unrelated files or whole-folder OCR/searchability work.

## 0.1.7

### Changed
- Agent instructions now frame dnr as an opportunistic cache, not a pre-transcription crawler:
  agents should first use cached/indexed knowledge and only record transcripts for files they
  already need to read for the current task.

## 0.1.6

### Changed
- Agent instructions now treat in-file embedding as the default storage mode and tell agents not
  to ask about storage unless the user explicitly requests byte-identical/db-only storage.

## 0.1.5

### Added
- `dnr init --global-agent` appends or upgrades a persistent dnr-first habit in the
  current agent's global instruction file (`codex`, `claude`, `all`, or an explicit path).
- The dnr skill now tells agents to persist that global habit on first use when supported.

## 0.1.4

### Changed
- Agent-file bootstraps now name the exact PyPI package and preferred `uvx` runner, and
  `dnr init --agent-file PATH` upgrades the older URL-only bootstrap in place.

## 0.1.3

### Added
- `dnr init --agent-file PATH` appends the one-line dnr bootstrap to agent instruction files
  such as `AGENTS.md` or `CLAUDE.md`; repeat the flag to update multiple files.

## 0.1.2

### Fixed
- `dnr index` now invalidates stale db-only records when the source file changes, so `dnr query`
  no longer returns old transcripts after a docx/`--no-embed` source edit.
- `--where` filters now reject multi-statement, DDL/DML, subquery, and unknown-column expressions
  instead of passing arbitrary raw SQL straight through.
- README, spec, security notes, and the agent skill now consistently describe the current
  no-sidecar/db-only storage model and the published PyPI release state.

## 0.1.1

### Fixed
- `dnr --version` now reflects the installed package version (read from package metadata,
  single source of truth) instead of a stale hard-coded string.

## 0.1.0

First public release.

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
