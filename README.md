# donotreadagain (`dnr`)

> **Read once, never again.** Embed a faithful, signed AI transcript into each expensive-to-parse file's own metadata, so AI agents stop re-OCR/re-parsing the same PDF, image, scan, or audio every time.

[![ci](https://github.com/melodysdreamj/donotreadagain/actions/workflows/ci.yml/badge.svg)](https://github.com/melodysdreamj/donotreadagain/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/donotreadagain)](https://pypi.org/project/donotreadagain/) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml) · status: v0.1 early release

---

## The problem

AI agents re-parse the same file *every time they touch it* — re-OCR a scan, re-run vision on a screenshot, re-transcribe an audio clip, re-extract a PDF. It's slow, it burns tokens and model calls, and it's non-deterministic. In **repeat-access corpora** (legal, research, compliance) the same documents get read dozens of times; with **multi-agent** setups every agent re-parses independently. The waste compounds exactly where it hurts.

## The idea

dnr reads a file **once**, then writes a verbatim transcript + structured metadata **into the file's own native metadata slot** as a *signed* JSON record — the file becomes **self-describing**. Any agent that opens it later reads the cached transcript instead of re-parsing. A per-folder SQLite + FTS5 index makes a whole folder searchable without opening anything.

The second view is the win:

| | first view (re-parse) | second view (cached) |
|---|---|---|
| born-digital PDF | ~1.4 s (pypdf) | ~60 ms — **~22× faster** |
| image / scan / audio | a vision / Whisper model call | a few ms of text — **no model at all** |

…and the cache is **trustworthy**: a record is used only if it's signed by a trusted key *and* its `content_hash` still matches the file, so "fast" never means "stale or forged."

## Demo

```console
$ dnr ingest contract.pdf            # transcribe once → sign → embed in the file
ingested contract.pdf  [in-file]
  method=text-extract transcriber=pypdf
  signed key_id=ce6d170a497238f7

$ dnr read contract.pdf              # later (or from any agent): verified cache hit — no re-parsing
LOAN AGREEMENT
Lender: Acme Capital LLC
Borrower: Jordan Smith
Principal: USD 1,200,000
...

$ dnr index ./contracts
$ dnr query ./contracts --match damages --context 40    # search a whole folder, no files opened
contract.pdf
    … Principal: USD 1,200,000  Maturity: 2026-12-31  Damages clause: section 7.
```

The transcript lives *inside* `contract.pdf` — move it, email it, hand it to another agent, and the cached transcript travels with it.

## Quickstart

Requires **Python 3.10+** (its stdlib includes the `sqlite3` used to read the index — one dependency covers both).

```bash
# run with no persistent install:
uvx --from donotreadagain dnr <cmd>
# or install:
pipx install donotreadagain        # or: pip install donotreadagain
```

```bash
dnr ingest report.pdf              # transcribe once (local) → sign → embed in the file
dnr read   report.pdf              # print the cached transcript (verified), or fall back
dnr index  ./case-folder           # build .dnr.db
dnr query  ./case-folder --match "손해배상" --tag 가압류 --since 2025-01-01
```

For a scan / image / anything you must *look* at, the agent transcribes it and records the result:

```bash
dnr record scan.png --transcript-file t.md --method vision --transcriber <your-model>
```

## How it fits together

```
File = canonical truth                    Index .dnr.db = derived, regenerable
┌────────────────────────────┐  harvest  ┌────────────────────────────┐
│  signed dnr record          │ ───────▶  │  fixed table + FTS5 search  │
│  content_hash · transcript  │           │  path · tags · transcript … │
│  provenance · fields · sig  │           └────────────────────────────┘
└────────────────────────────┘                 ▲ query via sqlite3 — no dnr install needed
   ▲ transcribe · sign · embed once (expensive)
```

**Where the record lives (no sidecar files):**
- **In-file** for formats with a metadata slot — PDF→XMP, MP3→ID3, PNG→iTXt, JPEG→APP segment. Pixels/bytes-of-content untouched (`content_hash` invariant), so the transcript **travels with the file** (move it, email it — it's still there).
- **db-only** in the folder's `.dnr.db` for formats with no slot yet (docx, …), or via `--no-embed` for evidentiary originals you must not modify (file left byte-identical). db-only records are folder-scoped; if the source file changes, the stale record is removed and the file must be re-ingested/re-recorded.
- **Nothing** for already-readable text (`.txt`/`.md`/`.csv`) — an agent just reads it.

**Current format support:**

| Format | Transcription | Record storage | Status |
|---|---|---|---|
| PDF | local text layer (`pypdf`) or agent vision for scans | XMP in-file | partial |
| PNG / JPEG | agent-supplied vision transcript | PNG iTXt / JPEG APP in-file | implemented |
| MP3 / WAV | local Whisper provider, if installed | MP3 ID3 in-file / WAV db-only | partial |
| DOCX | local `python-docx` text extraction | db-only | implemented |
| XLSX / PPTX / video / other office/media | planned providers | db-only until carriers land | planned |

## Using it

- **Read (consumer):** `dnr read <file>` returns the cached transcript only if it's present, trusted, and still matches (self-validating — a changed file silently misses). No dnr tool? An agent can read `.dnr.db` directly with ambient `sqlite3` (the db's `_dnr_readme` table self-describes).
- **Transcribe (producer):** `dnr ingest` (local: pypdf / Whisper / python-docx) or `dnr record` (agent supplies a vision transcript). dnr **owns no model** — the transcript is an input from whoever's best placed.
- **Query a folder:** `dnr query <folder>` combines `--match` (FTS, Korean/CJK ok) ∩ `--tag a,b` ∩ `--since/--until` ∩ restricted `--where` over fixed columns; plus `--any` (OR sweep), `--dedup`, `--context` (KWIC), `--format json`. Save composed queries with `--save`/`--use`; accumulate labels with `dnr tag`.
- **Agents onboard once:** point an agent at a dnr folder and it fetches **[SKILL.md](SKILL.md)** once — then it knows dnr everywhere. `dnr init` just ensures a signing key by default; to persist the one-line bootstrap in an agent instruction file, run `dnr init --agent-file AGENTS.md` (or `--agent-file CLAUDE.md`).

## Design principles

- **dnr is the deterministic substrate; the agent is the intelligence.** dnr does verifiable primitives (hash, sign, full-text/structured query); it never *infers* metadata (dates, parties, topics) or does fuzzy semantic search — that's the agent's job. Set metadata explicitly with `dnr tag` / `dnr date`.
- **File = truth, index = regenerable cache.** Delete `.dnr.db` and rebuild it from the files anytime.
- **Transcriber-agnostic.** dnr ships a *contract* (the verbatim guide) + a *trust layer*, not a model. Fidelity is the transcriber's; provenance is recorded so a consumer can apply its own quality policy (`trusted ≠ faithful`).

## Status & honest limits

v0.1 early release. Published on PyPI as `donotreadagain` and usable via `uvx`, `pipx`, or `pip`. Works today for repeat-access corpora; validated by real-corpus dogfooding. Known limits we're explicit about:
- **Adoption is the real lever.** The value compounds when agents *know* dnr (a skill, eventually native support) — not from the tool alone.
- **`trusted ≠ faithful`.** A signature proves *who made it + that it matches the file*, not that the transcription is accurate. Low-quality/garbled transcripts are flagged (`dnr status`), not silently trusted.
- **Coverage is still growing.** PDF/PNG/JPEG/DOCX are useful today; OOXML in-file carriers, more audio/video containers, pre-query auto-scan, and larger-corpus concurrency are still roadmap work.
- **Benchmarks are early.** The README numbers are illustrative dogfood timings; see [BENCHMARKS.md](BENCHMARKS.md) and [experiments/content-hash-invariance](experiments/content-hash-invariance) for the current proof/measurement status. A broader latency/token benchmark remains a release-readiness item.
- **Python is currently required.** A standalone binary for Python-less environments is future work.

See **[vision.md](vision.md)** (design) · **[spec/dnr-0.1.md](spec/dnr-0.1.md)** (spec) · **[SECURITY.md](SECURITY.md)** (threat model) · **[qna.md](qna.md)** (settled design decisions) · **[MILESTONES.md](MILESTONES.md)** (roadmap).

## Development

```bash
git clone https://github.com/melodysdreamj/donotreadagain
cd donotreadagain
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                       # the suite is green and fast
```

Contributions welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. Release automation is documented in **[RELEASING.md](RELEASING.md)**.

## License

[MIT](LICENSE) © 2026 june lee
