# dnr benchmarks

Status: early. The current repo has proof-oriented experiments and dogfood timings, not a
full public benchmark suite yet.

## What is already measured

- `experiments/content-hash-invariance/RESULTS.md` records the make-or-break carrier test:
  PDF `content_hash` stays stable across metadata embedding and common PDF re-save modes, while
  deterministic embedding avoids whole-file hash drift.
- The README's "second view" numbers are illustrative dogfood timings for the intended shape of
  the win: first parse/transcribe once, then later reads use verified text from the record/index.

## Release benchmark target

Before treating dnr as more than an early release, measure at least:

- Read latency: cold parse/transcribe vs verified `dnr read` for PDF, PNG/JPEG, DOCX, and audio.
- Query latency: `dnr index` first scan, incremental re-scan, and `dnr query` over a folder corpus.
- Token/model savings: repeated agent reads with and without cached transcripts.
- Storage impact: in-file record size, db-only index size, and backup/dedup churn from metadata writes.
- Freshness behavior: source edit invalidates stale db-only rows; in-file tamper/hash mismatch refuses cache hits.

## Suggested reporting shape

Use a table per corpus:

| Corpus | Files | First read/transcribe | Cached read | Index size | Notes |
|---|---:|---:|---:|---:|---|
| Legal PDFs | TBD | TBD | TBD | TBD | CJK search, text layer vs scan |
| Images/scans | TBD | TBD | TBD | TBD | agent-supplied vision transcript |
| Office docs | TBD | TBD | TBD | TBD | db-only until OOXML carrier lands |

Always publish the machine, Python version, dependency versions, corpus composition, and whether
times are cold or warm cache.
