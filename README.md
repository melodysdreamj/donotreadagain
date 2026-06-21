# donotreadagain (`dnr`)

> **Read once, never again.** Cache faithful, signed transcripts for expensive-to-parse files, so AI agents stop re-OCR/re-parsing the same PDF, image, scan, spreadsheet, or audio every time.

[![ci](https://github.com/melodysdreamj/donotreadagain/actions/workflows/ci.yml/badge.svg)](https://github.com/melodysdreamj/donotreadagain/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/donotreadagain)](https://pypi.org/project/donotreadagain/) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml) · status: v0.2 early release

**Tell your agent:**

```text
Use dnr for this folder.
```

That one line is the adoption path. The agent fetches **[SKILL.md](SKILL.md)**, checks cached
transcripts before parsing files, and records any expensive read it had to do anyway.

dnr is both a **reference CLI implementation** and a small
**[source-file transcript cache protocol](PROTOCOL.md)** for verified transcript records.
Harnesses can call the CLI today or implement compatible records
natively later.

---

## The problem

AI agents re-parse the same file *every time they touch it* — re-OCR a scan, re-run vision on a screenshot, re-transcribe an audio clip, re-extract a PDF. It's slow, it burns tokens and model calls, and it's non-deterministic. In **repeat-access corpora** (legal, research, compliance) the same documents get read dozens of times; with **multi-agent** setups every agent re-parses independently. The waste compounds exactly where it hurts.

## The idea

dnr is the **cache/trust/index layer** for expensive source-file reads and the reference
implementation of the **[DNR transcript cache protocol](PROTOCOL.md)**. A local extractor,
local ASR model, or the calling AI agent
reads a file once; dnr stores the resulting transcript + structured metadata as a *signed* JSON
record in a folder `.dnr.db` by default, so original files stay byte-identical. Any agent that
opens it later reads the cached transcript instead of re-parsing. A per-folder SQLite + FTS5
index makes a whole folder searchable without opening anything. Portable in-file records remain
available with explicit `--embed`, but file modification is never the default.

The second view is the win:

| | first view (re-parse) | second view (cached) |
|---|---|---|
| born-digital PDF | local text extraction (PyMuPDF→pypdf) | ~60 ms — no PDF parse |
| image / scan / audio | a vision / Whisper model call | a few ms of text — **no model at all** |

…and the cache is **trustworthy**: a record is used only if it's signed by a trusted key *and* its `content_hash` still matches the file, so "fast" never means "stale or forged."

## Agent contract

For agents and harnesses, dnr is a small pre-read loop:

1. **Known file:** run `dnr read <file>` before parsing it. If stdout has text, use it and do not re-read.
2. **Miss:** if the task still needs the file, parse/look/listen once, then cache that result with `dnr ingest` or `dnr record`.
3. **Folder question:** run `dnr index <folder>`, then `dnr query <folder> ...` before opening files.
4. **Folder preparation:** use `dnr status <folder> --pending`; run `dnr backfill <folder>` only when the user wants a folder pass.
5. **Boundary:** never bulk-transcribe just because files are pending; only cache work the task actually needs.

Harness maintainers can copy the integration contract and reference adapters from
**[HARNESS.md](HARNESS.md)**, or implement the protocol directly from **[PROTOCOL.md](PROTOCOL.md)**.

## Demo

```console
$ dnr ingest contract.pdf            # transcribe once → sign → cache in .dnr.db
ingested contract.pdf  [db-only (index)]
  method=text-extract transcriber=pymupdf
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

The transcript lives in the folder's `.dnr.db` by default, so `contract.pdf` itself stays untouched.
If you explicitly need the cache to travel inside the file, add `--embed`.

## Quickstart

Recommended install:

```bash
pipx install donotreadagain
dnr --version

# one-off/fallback when installing is not available:
uvx --from donotreadagain dnr <cmd>

# audio ASR:
pipx inject donotreadagain faster-whisper   # ffmpeg may also be needed for decoding
```

```bash
dnr ingest report.pdf              # extract once (local) → sign → store in .dnr.db
dnr backfill ./case-folder         # folder pass: local-provider files now, agent/vision worklist after
dnr read   report.pdf              # print the cached transcript (verified), or fall back
dnr index  ./case-folder           # build .dnr.db
dnr status ./case-folder --pending # honest usable/pending/repair coverage
dnr query  ./case-folder --match "손해배상" --tag 가압류 --since 2025-01-01
```

For a scan / image / anything you must *look* at, the agent transcribes it and records the result:

```bash
dnr record scan.png --transcript-file t.md --method vision --transcriber <your-model>
```

## How it fits together

```
File = canonical truth                    Index .dnr.db = default cache
┌────────────────────────────┐  harvest  ┌────────────────────────────┐
│  original file bytes         │ ───────▶  │  signed record + FTS5 search │
│  content_hash · transcript  │           │  path · tags · transcript … │
│  provenance · fields · sig  │           └────────────────────────────┘
└────────────────────────────┘                 ▲ query via sqlite3 — dnr CLI optional for reads
   ▲ transcribe once · sign · store db-only (expensive)
```

**Where the record lives (no sidecar files):**
- **db-only by default** in the folder's `.dnr.db`, so original files stay byte-identical. If the source file changes, the stale record is removed and the file must be re-ingested/re-recorded.
- **Optional in-file** with explicit `--embed` for formats with a metadata slot — PDF→XMP, MP3→ID3, M4A/MP4/MOV→MP4 freeform atom, FLAC/OGG/OPUS→Vorbis/Opus comments, PNG→iTXt, JPEG→APP segment. This makes the transcript travel with the file, but it rewrites file bytes and is never the default.
- **Nothing** for already-readable text (`.txt`/`.md`/`.csv`) — an agent just reads it.

**Current format support:**

| Format | Transcription | Record storage | Status |
|---|---|---|---|
| PDF | local text layer (`PyMuPDF` first, `pypdf` fallback) or agent vision for scans | db-only default; optional XMP with `--embed` | partial |
| PNG / JPEG | agent-supplied vision transcript | db-only default; optional PNG iTXt / JPEG APP with `--embed` | implemented |
| HEIC / HEIF | agent-supplied vision transcript; optional `pillow-heif` hash | db-only | partial |
| MP3 / WAV / M4A / FLAC / OGG / OPUS | local Whisper provider via `donotreadagain[audio]`, if installed | db-only default; optional in-file for non-WAV carriers with `--embed` | partial |
| DOCX | local `python-docx` text extraction | db-only | implemented |
| XLSX | local `openpyxl` sheet extraction | db-only | implemented |
| MP4 / MOV video | agent-supplied transcript/ASR+vision | db-only default; optional MP4 freeform with `--embed` | partial |
| PPTX / other office/media | planned providers or agent-supplied transcript | db-only until carriers land | planned |

## Using it

- **Read (consumer):** `dnr read <file>` returns the cached transcript only if it's present, trusted, and still matches (self-validating — a changed file silently misses). No dnr tool? An agent can read `.dnr.db` directly with ambient `sqlite3` (the db's `_dnr_readme` table self-describes).
- **Transcribe (producer):** `dnr ingest` (local: PyMuPDF→pypdf / python-docx / openpyxl / optional faster-whisper) or `dnr record` (agent supplies a vision/OCR transcript). dnr is an opportunistic cache: do this when the current task already requires reading/parsing that file, not just because a folder has pending files. If a needed file's cached transcript is empty/garbled/unusable, repair that file immediately; ask only before expanding into whole-folder OCR/searchability work.
- **Backfill a folder:** `dnr backfill <folder>` (also `dnr ingest <folder>`) ingests locally-processable files in one pass, skips already-readable text, and prints a worklist for images/scans/videos or low-quality results that need agent/vision repair.
- **Query a folder:** `dnr query <folder>` combines `--match` (FTS, Korean/CJK ok) ∩ `--tag a,b` ∩ `--since/--until` ∩ restricted `--where` over fixed columns; plus `--any` (OR sweep), `--dedup`, `--context` (KWIC), `--format json`. Save composed queries with `--save`/`--use`; accumulate labels with `dnr tag`.
- **Agents onboard locally:** point an agent at a dnr folder and it fetches **[SKILL.md](SKILL.md)** once for that task/folder. Recommended install is `pipx install donotreadagain`; one-off fallback is `uvx --from donotreadagain dnr ...`. `dnr init` just ensures a signing key by default; to persist the bootstrap in a project instruction file, run `dnr init --agent-file AGENTS.md` (or `--agent-file CLAUDE.md`). Harness authors can integrate the same read-through cache hook with **[HARNESS.md](HARNESS.md)**.

## Design principles

- **Protocol first, CLI as proof.** The DNR transcript cache protocol is the portable contract; `dnr` is the
  reference implementation that proves it works and gives harnesses an optional hook today.
- **Original files stay untouched by default.** The default write path is `.dnr.db`; in-file records
  require explicit `--embed`.
- **Not a general knowledge format.** dnr stores faithful transcripts tied to original files.
  Curated concepts, runbooks, summaries, and knowledge-base pages belong in higher-level docs;
  dnr can feed those systems, but it is not trying to replace them.
- **dnr is the deterministic substrate; the agent is the intelligence.** dnr does verifiable primitives (hash, sign, full-text/structured query); it never *infers* metadata (dates, parties, topics) or does fuzzy semantic search — that's the agent's job. Set metadata explicitly with `dnr tag` / `dnr date`.
- **File = truth, index = regenerable cache.** Delete `.dnr.db` and rebuild it from the files anytime.
- **Transcriber-agnostic.** dnr ships a *contract* (the verbatim guide) + a *trust layer*, not a model. Fidelity is the transcriber's; provenance is recorded so a consumer can apply its own quality policy (`trusted ≠ faithful`).

## Status & honest limits

v0.2 early release. Published on PyPI as `donotreadagain`; the recommended path is `pipx install donotreadagain`. `uvx` remains a one-off/fallback path, but it still requires uv and can be slower than a normal install for repeated use. Standalone binaries remain a future packaging option for Python-less environments. Works today for repeat-access corpora; validated by real-corpus dogfooding. Known limits we're explicit about:
- **Adoption is the real lever.** The value compounds when agents *know* dnr (a skill, eventually native support) — not from the tool alone.
- **`trusted ≠ faithful`.** A signature proves *who made it + that it matches the file*, not that the transcription is accurate. Low-quality/garbled transcripts are flagged (`dnr status`), not silently trusted.
- **Coverage is still growing.** PDF/PNG/JPEG/HEIC/DOCX/XLSX and common audio containers are useful today; OOXML carriers, more video containers, pre-query auto-scan, and larger-corpus concurrency are still roadmap work.
- **Benchmarks are early.** The README numbers are illustrative dogfood timings; see [BENCHMARKS.md](BENCHMARKS.md) and [experiments/content-hash-invariance](experiments/content-hash-invariance) for the current proof/measurement status. A broader latency/token benchmark remains a release-readiness item.
- **Python packaging is the product path.** Use `pipx` for the cleanest install; `uvx` remains the one-off/fallback route.

See **[PROTOCOL.md](PROTOCOL.md)** (portable transcript-cache protocol) · **[HARNESS.md](HARNESS.md)** (harness integration) · **[vision.md](vision.md)** (design) · **[spec/dnr-0.1.md](spec/dnr-0.1.md)** (record spec) · **[SECURITY.md](SECURITY.md)** (threat model) · **[qna.md](qna.md)** (settled design decisions) · **[MILESTONES.md](MILESTONES.md)** (roadmap).

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
