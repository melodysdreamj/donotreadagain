# donotreadagain (dnr)

> **Read once, never again.** Transcribe an expensive file once, then write the result into the file itself — a self-describing-file spec + thin tool so AI agents never re-parse the same file.

This is the dnr **vision / design document**. The formal spec (`spec/dnr-0.1.md`) and the implementation derive from it.

---

## 0. TL;DR

Take an expensive-to-read file (PDF, audio, video, image, office), **transcribe it once, faithfully**, and **embed that transcript + metadata into the file's own native metadata slot as a unified, signed JSON record.** The file becomes "self-describing": any agent that opens it uses the transcript directly instead of re-parsing. A per-folder **regenerable index** (`.dnr.db`) backs cross-file queries.

- **File = canonical truth** (location-independent, signed)
- **Index = derived cache** (regenerable anytime)
- **No-install consumption**: an AI just reads with `sqlite3` / `exiftool`; only production (transcribe + embed) runs on demand via `uvx`.

---

## 1. The problem (Why)

An AI harness re-runs OCR / transcription every time it reads the same PDF or audio file — a waste of time, tokens, and money. Transcription is deterministic work, so it should be **done once and cached**. Existing caches keep the result in an external store only; dnr **carries the result in the file itself**, so the file describes itself wherever it goes.

---

## 2. The core idea — self-describing files

1. Transcribe the file once (verbatim, see §8).
2. Pack the transcript + provenance + queryable fields + a signature into **a single JSON record**.
3. Embed that record into the **file's native metadata slot** (PDF→XMP, mp3→ID3, …).
4. A consumer (AI) checks for the record first; **if it verifies, it uses the transcript as-is and skips re-parsing.**
5. Indexing a folder collects the records into a queryable table.

---

## 3. Architecture — two layers

```
File (canonical truth, location-independent)   Index .dnr.db (derived, regenerable)
┌────────────────────────────┐                ┌──────────────────────────────┐
│ dnr record (XMP/ID3 slot)   │   harvest      │ core columns + fields/extras   │
│  content_hash, transcript,  │ ─────────────▶ │ + path, whole_hash, mtime      │
│  provenance, fields, sig    │                │ + FTS5 (full-text)             │
└────────────────────────────┘                └──────────────────────────────┘
   ▲ expensive: transcribe·embed·sign once       ▲ cheap: regenerate anytime
   producer (uvx, once)                           consumer = AI (sqlite3, no install)
```

**Division of labor — the file holds "content facts" only; the index holds "location / catalog facts" only.**

| Info | Where | Why |
|---|---|---|
| content_hash, transcript, provenance, fields, sig | **file + index** | true wherever it lives (location-independent) |
| path | **index only** | changes on move (if the file held its own location, every move would rewrite it) |
| whole_hash | **index only** | hash of the whole file bytes — can't store a hash of itself inside itself (chicken-and-egg) |
| mtime, indexed_at | **index only** | filesystem / catalog bookkeeping |

Test: *"If I emailed this file with no index, should this fact travel with it?"* → if yes, file; if no, index.

---

## 4. Record schema (what's embedded in the file)

```jsonc
{
  "dnr": "0.1",                          // version = "this file has a dnr record" marker
  "content_hash": "sha256:…",            // decoded-content hash (identity + invalidation key, §6)
  "source": {
    "mime": "application/pdf",
    "bytes": 184213,
    "pages": 42
  },
  "transcript": {                        // ← verbatim & complete. NOT a summary (§8)
    "format": "text/markdown",
    "lang": "ko",
    "text": "# Judgment…\n…full body, verbatim…",
    "segments": [ { "t": 0.0, "text": "…" } ]   // time-coded, for A/V, optional
  },
  "provenance": {                        // "how it was transcribed" (§8)
    "method": "vision",                  // text-extract | vision | ocr | asr | none
    "transcriber": "claude-opus-4-vision",
    "version": "…",
    "instruction_id": "dnr-verbatim-1",  // which transcription contract was followed
    "prompt_hash": "sha256:…",           // hash of the actual prompt
    "params_hash": "sha256:…",
    "confidence": 0.94,
    "created_at": "2026-06-20T08:00:00Z"
  },
  "fields": {                            // queryable columns (free to add domain keys)
    "title": "…",
    "summary": "…",                      // explicitly lossy summary (≠ transcript)
    "start_date": "2024-04-01",
    "tags": ["contract", "damages"]
  },
  "extras": { },                         // format-specific byproducts (duration, sheet count, …)
  "sig": {                               // signature (§9)
    "alg": "ed25519",
    "key_id": "…",
    "value": "base64…"                   // sign(JCS(record − sig))
  }
}
```

- `path` and `whole_hash` are **not here** (index only, §3).
- `transcript` (verbatim & complete) and `fields.summary` (lossy summary) are **never conflated** (§8).
- **Already-text files** (txt/csv/json/md) omit `transcript` and use `method: "none"` (no transcription). Only `fields` is filled, via a sidecar, to join the index; the body is read directly from the original by the index (§15).

---

## 5. Carrier mapping — one JSON, N slots

The same JSON record is stored as a string in each format's **dedicated third-party slot**. A unique key (`dnr`) avoids clashing with native tags.

| Format | canonical slot |
|---|---|
| PDF · JPEG · PNG · TIFF · MP4/MOV | XMP, namespace `dnr`, property `dnr:record` |
| MP3 | ID3v2 `TXXX:dnr` |
| FLAC · OGG | Vorbis comment `DNR=` |
| M4A | MP4 atom |
| docx · xlsx · pptx | OOXML custom XML part |
| no slot · unwritable · oversized · sensitive | **sidecar** `<file>.dnr.json` |

The indexer parses the record as *the same JSON regardless of where it was extracted from*.

---

## 6. content_hash — deterministic, per-format canonical

**The single most important primitive.** Cache validity, the re-transcribe decision, and move-matching all hang on it.

### Why decoded content, not raw bytes
"Take the file bytes minus the metadata region" is **not deterministic** for PDF/OOXML — libraries re-serialize the whole container on save (object renumbering/reordering, Flate recompression, ZIP recompression). So we hash the **decoded content** instead.

### Per-format definition
- **PDF** = `sha256( per page, in order: decompressed content-stream bytes ++ image XObject bytes )`
  - **Invariant** under object reordering, Flate recompression, and metadata writes; sensitive to real content edits.
  - Condition: embedding **must not re-encode** content/image streams (conformance gate, §16).
- **mp3 · FLAC** = `sha256( audio frame bytes, excluding ID3/Vorbis tags )`
- **Image (JPEG/PNG)** = `sha256( decoded pixels + dimensions )`
- **OOXML** = `sha256( sorted manifest of (member-path, hash-of-decompressed-member), excluding the dnr part )`

### Pinned normalization (spec v0.1)
- Hash algorithm: **SHA-256**
- Record JSON: **RFC 8785 JCS** (canonical serialization)
- All text: **NFC** normalization
- Named extraction **profile id** (`dnr-pdf-content-1`, …) — hashes only guaranteed to match within the same profile
- **Golden test vectors** published (cross-implementation self-check)

---

## 7. Cache invalidation — three hash triggers

Layered cheap → expensive:

| What changed | Signal | Result |
|---|---|---|
| nothing | stat(size, mtime) identical | **skip** (don't open the file) |
| metadata only (tags, …) | only whole_hash changed | **re-index only** (no re-transcribe) |
| body (content) | **content_hash changed** | **re-transcribe** + re-index |
| a better model shipped | compare transcriber/version | **deliberate re-transcribe** |

Key: **the re-transcribe trigger is only a `content_hash` change OR a model upgrade.** If the file bytes change but the content didn't (metadata only), the expensive transcription does not run. Per-`method` precision is possible — when a new ASR ships, re-transcribe only the `asr` records and skip `text-extract`.

A move (`mv`) leaves bytes unchanged → hashes unchanged → only the index `path` column is updated, zero re-transcription.

---

## 8. Transcription contract

**For "skip re-parsing" to be legitimate, reading the transcript must equal reading the original.** If the transcript were a summary, information is lost and the premise collapses. Therefore:

### Principle: transcript = verbatim & complete
- The entire content, nothing omitted — no truncation, no "…", no "rest omitted"
- **No summarizing, paraphrasing, or commentary**; preserve original order & structure (headings/lists/tables/page breaks/speakers/timestamps)
- Tables as structure (markdown tables), not prose summaries
- Uncertain / illegible parts marked explicitly, not guessed or dropped (`[illegible]`, `[unclear: …]`)
- Preserve language (mark it if translated)
- `transcript` (verbatim) ≠ `fields.summary` (explicitly lossy) — **never conflated**

### Method hierarchy (text-extract > vision > ~~ocr~~)

| method | typos | hallucination | trust | when |
|---|---|---|---|---|
| **text-extract** | none | none | **highest** | a clean text layer exists (lossless, free) |
| **vision (model)** | few | rare (caught by verification) | high | scans, images, layout/tables matter |
| ~~ocr (traditional)~~ | **many** | none | low | offline / extreme cost-saving last resort only |
| `none` | — | — | — | already-text files (txt/csv/json/md) — no transcription, fields only |

**Traditional OCR has too many typos to meet the verbatim goal** → demoted from the recommended path. Default is *"extract if there's a text layer, otherwise vision model."* The vision model's rare failures (hallucination/omission) are caught by the verbatim contract plus, for high-stakes (legal etc.), **cross-check / double-pass diff**. As of 2026, vision LLMs have effectively replaced OCR.

### Recording (provenance)
Stamp `method` + `transcriber` + `version` + `instruction_id` + `prompt_hash` so **"what method/model/instruction produced this verbatim"** is verifiable and reproducible. `method` alone tells you the trust level.

> Honest limit: verbatim drives *design-level loss (summarization)* to zero. *Extraction errors* (model hallucination, etc.) are surfaced via `method` + `confidence`, and high-stakes cases are reinforced with a verify mode.

---

## 9. Signing & trust

An unsigned record is defenseless against forgery, prompt injection, and poisoning. So **records are signed.**

- `record_hash = sha256(JCS(record − sig))`, signed with **Ed25519** (64-byte sig, 32-byte pubkey — trivial to fit in metadata).
- The record binds two things: `content_hash` (record ↔ content) + `sig` (record ↔ producer).
- **Consumer trust tiers:**

| State | Action |
|---|---|
| signed by a trusted key ✓ **AND** recomputed content_hash matches ✓ | **skip-reparse allowed** (use the transcript as-is) |
| unsigned · untrusted key · hash mismatch | **search/index only**; read the original normally; wrap the transcript as "untrusted data" and **never feed it as instructions** |

Single user: one local keypair + just your own pubkey in the trust list → instantly rejects forged records in files made by others. **Compatible with no-install** (verification needs only a pubkey file).

---

## 10. Consumer contract

- **Read:** if a record exists (signature trusted + content_hash matches) → use the transcript, skip re-parsing. Otherwise → read normally (**not an error — fall back**).
- **Self-population (lazy):** when a file is *actually read* and isn't transcribed yet, transcribe just that one file (a cost you'd pay anyway). **But if answering a query would require pre-transcribing many files → ask the user and do only the approved ones** (prevents a cost blow-up). A whole folder is an explicit `dnr ingest`.
- **Move resilience:** identity is content_hash → a move only updates the index path.
- **Security posture:** an embedded record is **untrusted by default**. Trust is earned only via signature + hash. The transcript is never treated as instructions.
- **Additive:** a file with no record behaves exactly as today (no regression). But "zero-risk" does NOT hold when *an adopter meets a malicious file* → which is why signing is mandatory.

---

## 11. Index

One hidden file per folder, **`.dnr.db`** (SQLite + FTS5, later sqlite-vec). Travels with the folder, **regenerable** — the truth is in the files.

> **index ≠ ingest.** Indexing is the cheap job of *harvesting records already embedded* (no transcription). Transcribe + embed (ingest) is separate. Indexing and querying are **enforced via the CLI** (`dnr index` / `dnr query`) — prose instructions are followed unreliably by models.

### Base table = a fixed contract (name, columns, types all pinned by the spec)

An agent receives this schema **injected via a skill** in advance, so it can **query immediately** on encountering any `.dnr.db` with no introspection. This is what makes "queries portable."

```sql
CREATE TABLE dnr (                 -- table name 'dnr' is fixed
  content_hash TEXT PRIMARY KEY,   -- identity / join key
  path         TEXT NOT NULL,      -- current location
  mime         TEXT,
  bytes        INTEGER,
  mtime        INTEGER,
  indexed_at   TEXT,
  method       TEXT,               -- text-extract|vision|ocr|asr|none
  transcriber  TEXT,
  version      TEXT,
  lang         TEXT,
  title        TEXT,
  summary      TEXT,
  tags         TEXT,               -- JSON array
  transcript   TEXT,               -- body (FTS source)
  fields       TEXT,               -- JSON: domain fields (start_date, court…)
  extras       TEXT                -- JSON: format-specific (duration…)
);
CREATE VIRTUAL TABLE dnr_fts USING fts5(title, summary, transcript, content='dnr');
CREATE TABLE _dnr_readme(...);     -- self-description (in-band backup for skill-less agents)
```

**Two things the spec must enforce so blind queries don't break:**
1. **Fixed names** — the table is always `dnr`, full-text is always `dnr_fts`.
2. **Fixed types (affinity)** — SQLite is dynamically typed, so if affinity varied per folder, queries would diverge → pin the types above normatively.

Example queries (the same in any dnr folder):
```sql
SELECT path FROM dnr WHERE method='vision' AND lang='ko';
SELECT path FROM dnr_fts WHERE dnr_fts MATCH 'damages';
SELECT path FROM dnr WHERE json_extract(fields,'$.start_date') > '2024-01-01';
```

### Beyond that, freedom
- Sub-tables, views, vector indexes, and *how* the index is built = the implementation's choice.
- **DuckDB** = an optional cross-folder query lens (ATTACH many `.dnr.db`), not the store.
- **Domain fields**: default is `fields` JSON + `json_extract` (still blind-queryable). If used often, promote to real columns via a **profile** (e.g. `legal` → court·case_no·start_date) — promotions are recorded in `_dnr_readme` so the agent knows.

**What the skill carries = ① the fixed schema above + ② example queries.** Hence immediate querying on first contact. A skill-less agent reads `_dnr_readme` once to bootstrap.

### Runtime behavior (build · query · concurrency)

- **index ≠ ingest** (restated): indexing *only harvests* (cheap); transcription is separate.
- **cold folder**: a never-ingested folder → harvest only existing records + text bodies; **media without records become "pending" rows** (path·hash, empty transcript). Transcription is an explicit `dnr ingest` or query-driven (§10: the agent asks, approved-only).
- **pre-query incremental scan**: `dnr query` runs a light stat scan right before querying to freshen the index — the ~99% unchanged are stat-skipped, nearly free. `--no-scan` to disable.
- **concurrency** (plain SQLite, *not Turso*): `.dnr.db` = **WAL mode** + write lock · duplicate transcription of the same file = a **per-content_hash lock** (claim) · embedding = **atomic temp+rename** · cross-machine = *don't sync the index; sync the files and regenerate locally* (the index is regenerable); file-record split-brain is resolved by signature + last-writer.

---

## 12. Distribution — no install

**"The AI is the runtime; the instructions are the program."**

- **Consumption (read/query)** = already-present tools like `sqlite3` / `exiftool`. Zero dnr install.
- **Production (transcribe/embed)** = `uvx donotreadagain ingest <file>` run on demand, once per file. No resident daemon, no mandatory MCP.
- The only genuinely heavy code is **transcription**. Embed/index/read are thin glue over ubiquitous tools.
- Discoverability: a copy-paste `AGENTS.md` stanza + `_dnr_readme` + a public spec URL.

---

## 13. Three non-negotiable safety items (mandatory once you choose embedding)

1. **Signing** — unsigned records can't unlock skip-reparse (§9).
2. **Atomic writes** — never modify the original in place. Write to a copy → verify content_hash unchanged + native tags preserved → swap in via temp+fsync+rename.
3. **Sidecar fallback** — oversized (large transcript), signed/read-only, confidential/evidentiary, or social-re-encoding-path files use `.dnr.json` instead of embedding.

---

## 14. Known risks (8-agent audit, honestly)

| Risk | Mitigation |
|---|---|
| content_hash non-deterministic via raw bytes on PDF/OOXML | **decoded-content hash + conformance gate** (§6, §16) |
| unsigned record = prompt-injection · forgery · TOFU poisoning | **Ed25519 signing + untrusted-by-default** (§9) |
| embed vs plain cache: low marginal value at n=1 | embedding is a bet on *self-description · portability · standard* ambition. Immediate value comes from the index/cache; the differentiator is in-file — carry both |
| AI summary/entity leakage on share / mutating legal originals | **sidecar default (risky files) + sensitivity flag + strip command** |
| adoption cold-start; OKF shipped a similar framing first | **single-user tool first**; co-emit OKF sidecars to coexist |
| write (transcription) cost + transcriber_version re-transcribe tax | one-time · cached + per-`method` precise re-transcribe (text-extract is exempt) |
| verbatim transcript = large payload | sidecar fallback absorbs it (§13) |

> The audit recommended "cache first, defer embedding," but for the **self-describing-file standard** vision we choose embed-first — while solving the prerequisites the audit set (canonical hash + signing) **first**.

---

## 15. Scope

dnr delivers **two separable values** — the scope per file differs:
1. **Transcription cache** (read the expensive thing once) — media only.
2. **Derived fields + unified index** (search/route by title/summary/tags/date) — useful for all files.

| File kind | Transcription | Joins index | Carrier |
|---|---|---|---|
| PDF · audio · video · image | ✅ verbatim | ✅ | in-file (or sidecar) |
| txt · csv · json · md (small) | ❌ `method:"none"` | ✅ fields-only | **sidecar only** (body read from the original) |
| large CSV/JSON/logs | ❌ | ✅ **summary + schema only** | sidecar (body handled by code/pandas) |

**Out of scope:**
- **No body copying** — don't copy an already-text file's body into the sidecar (duplication / sync risk). The index reads it straight from the original.
- **Signed / read-only files** — no mutation → sidecar or excluded.
- **Social / email re-encoding transport** — metadata stripping → can't trust in-file. dnr is trusted over blob-preserving transport (git/rsync/S3/NAS).

> Text-file support is a *uniformity bonus*, not the core (re-parsing expensive media) → **opt-in, later**. Add it after the media path is solid.

---

## 16. Roadmap — the v0.1 "core" first

Audit conclusion: until the below is frozen, everything else is unstable. **This is the real conformance surface.**

**Pillar 1 — Canonicalization core**: per-format content_hash (decoded) + SHA-256/JCS/NFC/profile/golden vectors.
**Pillar 2 — Signing core**: Ed25519 over JCS(record−sig) + trust tiers.
**Conformance gates** (tested per carrier):
1. `content_hash` unchanged after `embed(record)` (round-trip) — ✅ empirically shown for PDF/WAV (2026-06-20)
2. native tags preserved after `embed`
3. `embed` is **atomic** (temp+fsync+rename)
4. `embed` is **byte-deterministic** — `deterministic_id` + suppressed auto-timestamps keep whole_hash stable on re-embed (prevents re-index churn)

Targets: **PDF + mp3** first. Passing these technically rescues embed-first.

### 🔬 make-or-break experiment (first code)
```
real.pdf → content_hash(h0) → embed XMP → recompute == h0 ?
        → re-save with different options → recompute == h0 ?
mp3 the same (ID3 TXXX)
```
Directly validates the audit's #1 doubt (PDF non-determinism). Holds → pillar 1 proven. Breaks → that's the real constraint.

**Result (2026-06-20) — ✅ MAKE.** (`experiments/content-hash-invariance/`) PDF content_hash stayed **invariant** across default·object_streams·linearize·recompress·`normalize_content` (only whole_hash changed); the WAV audio payload was invariant under an ID3 write too. Finding: the default embed drifts whole_hash via a random `/ID` + `MetadataDate` → a **deterministic embed recipe** (`pikepdf.save(deterministic_id=True)` + `open_metadata(set_pikepdf_as_editor=False)` + deleting dates) makes re-embed byte-identical. → that is where gate 4 came from. Follow-ups remaining: real scanned PDF (image/JBIG2), multi-MB transcript, real mp3.

### After that
Index/FTS query → enforced `dnr read` CLI (protocol from prose → code) → format expansion → optional MCP / OKF emit.

---

## 17. Name

**donotreadagain**, CLI alias **dnr**. The value is in the name ("again" = caching). Tagline: *Read once, never again.*

---

## Appendix: positioning (vs prior art)

- **digiKam** — embed + local SQLite index + incremental. But photos only, no AI transcription. dnr = "digiKam generalized to all media + AI transcription as the payload."
- **C2PA** — cross-format in-file structured assertions. But for authenticity/signing, query-agnostic, hard-bound (breaks on edit). dnr = edit-tolerant · query-first.
- **Google OKF** (2026-06) — agent-knowledge sidecars (md + YAML). But not in-file, no media transcription. dnr = in-file + media transcription.
- **Framedex** — video sidecars + index. But sidecar only, video/photos only.
