# dnr — Milestones

Build roadmap. Full design → [vision.md](vision.md). &nbsp; Status: ✅ done · 🔜 in progress / next · ⬜ todo

**v0.1 goal —** a working `dnr` that ingests PDF + audio (transcribe → canonical-hash → deterministic embed → sign), builds a per-folder queryable index (Korean/CJK search included), and lets an agent read/query with **no install**. Fundamentals-first: the `content_hash` and signing primitives are *proven* before the rest is layered on.

**Critical path:** M1 → M2 → (M3 ∥ M4) → M5 → M6 → M7 → M8 → M9. &nbsp; **v0.1 cut** = M1–M8 (build) + **M9 (dogfood — the real release-readiness gate)**. &nbsp; **M10–M14** = operability, security, the standard, scale, release.

**Progress (2026-06-20):** package scaffolded (`src/dnr/`) — `hashing` (content_hash PDF/mp3/wav + whole_hash), `record` (RFC 8785 JCS), `embed` (PDF/mp3/sidecar; gates 1·2·4), `signing` (Ed25519 + trust list + forgery rejection). **22 tests green.** M1–M3 cores landed; remaining: golden vectors / cross-tool determinism, more carriers + proper `dnr:` namespace, NFC, keyring, full CLI.

---

## ✅ M0 — Foundation validated
> Prove the load-bearing assumption before building on it.
- [x] Design doc (`vision.md`) — architecture, schema, hashing, trust, distribution
- [x] Repo init (git, MIT, README, .gitignore)
- [x] **make-or-break experiment** — `content_hash` invariant under embed + every re-save mode (PDF/WAV)
- [x] Deterministic embed recipe found → conformance **gate 4**

## 🔜 M1 — Canonicalization core + conformance harness
> The single primitive everything rests on — *and* the test infra that makes "any tool agrees" real.
- [x] `content_hash(pdf)` — decompressed content streams + image XObjects, page order
- [~] `content_hash(audio)` done (mp3 frames + wav data chunk); remaining: `content_hash(image)` (decoded pixels), `content_hash(ooxml)` (member manifest)
- [~] Canonical record serialization — SHA-256 + RFC 8785 JCS done; NFC text normalization remaining
- [ ] **Conformance harness** — golden test vectors per format + a runnable suite, wired into **CI** (gates run every commit)
- [ ] **Cross-tool / cross-version determinism** — same `content_hash` across pikepdf/qpdf versions (and a 2nd library), not just self-consistency
- [ ] Follow-up validations: real **scanned** PDF (image-only), multi-MB payload, real **mp3**
- **Done when:** two independent tools/versions agree on `content_hash` for a real corpus, with published vectors.

## 🔜 M2 — Embed / extract engine (carriers)
> Write & read the record in each format's native slot, safely.
- [~] Write: **PDF (XMP) · mp3 (ID3 TXXX) · sidecar `.dnr.json`** done; remaining: proper `dnr:` namespace, JPEG/PNG/TIFF/MP4, Vorbis, OOXML
- [x] **Deterministic embed** (`deterministic_id`, no auto-timestamps) — gate 4
- [x] **Atomic write** (temp + fsync + rename) — never mutate the original in place
- [x] Preserve native tags (gate 2) · read-back + verify `content_hash` (gate 1)
- [ ] Sidecar fallback rules: no slot / over size limit / read-only / sensitive
- **Done when:** all 4 conformance gates pass per carrier in CI.

## 🔜 M3 — Signing & trust
> Make a record trustworthy enough to justify skipping a re-read.
- [x] `record_hash = sha256(JCS(record − sig))`, Ed25519 sign / verify
- [~] Keygen + trust list done; persistent local keyring remaining
- [ ] Verify → trust tiers: signed + trusted + hash-match → **skip-reparse**; else **search-only + fallback**
- [ ] `transcript` always handled as untrusted data, never as instructions
- **Done when:** forged / altered / untrusted-key records are correctly refused for skip-reparse.

## ⬜ M4 — Transcription (ingest)
> Turn a raw file into a faithful record, once.
- [ ] Method hierarchy: `text-extract` → `vision` model → (`ocr` demoted)
- [ ] **Verbatim** transcription contract (prompt): complete, no summary, mark uncertainty
- [ ] provenance: method, transcriber, version, instruction_id, prompt_hash, confidence
- [ ] Per-segment language tagging (feeds M6)
- [ ] Cost control: query-driven lazy ingest · ask-the-user · `dnr ingest --glob --budget`
- **Done when:** a PDF / audio ingests into a verbatim, signed, embedded record with provenance.

## ⬜ M5 — Index (query layer)
> A folder becomes a queryable table — cheaply, incrementally.
- [ ] `.dnr.db`: fixed base table (16 cols) + `dnr_fts` (FTS5) + `_dnr_readme`
- [ ] Incremental scan: stat → whole_hash → content_hash → harvest; tombstone deletes
- [ ] **index ≠ ingest**; cold folder = pending rows (no transcription)
- [ ] Pre-query incremental scan (`--no-scan` to skip)
- [ ] Move resilience: `content_hash` match → update `path` only
- [ ] Concurrency: SQLite **WAL** + `content_hash` ingest lock
- **Done when:** second scan is fast (stat-skips), queries are fresh, moves don't re-transcribe.

## ⬜ M6 — i18n & search quality
> Make non-English — especially Korean/CJK — actually searchable (the founder's own corpus).
- [ ] **ICU (or trigram) FTS5 tokenizer** — the default tokenizer mangles CJK; pin a Unicode-aware one
- [ ] NFC normalization end-to-end (hashing + indexing); RTL / bidi handling
- [ ] Multilingual `fields` consistency so cross-folder queries stay portable
- **Done when:** Korean legal-doc full-text search returns correct hits.

## ⬜ M7 — CLI & distribution
> One tool that ties it together, runnable anywhere.
- [ ] `dnr init | ingest | index | query | read | verify | seal | strip`
- [ ] Protocol enforced in code (not prose)
- [ ] `uvx` package **+ single static binary** (per-platform releases) — dependency-free drop-in
- **Done when:** `uvx dnr index <folder>` and `dnr query` work on a fresh machine, offline (minus transcription API).

## ⬜ M8 — Agent integration (consumer)
> Zero-install consumption by AI agents.
- [ ] `AGENTS.md` / skill stanza: fixed schema + example queries + consumer contract
- [ ] Consumer path: read record via ambient `sqlite3` / `exiftool` — no dnr install
- [ ] query-driven lazy-ingest behavior wired into the skill
- [ ] **One-phrase bootstrap** — `dnr init` self-installs the skill stanza into the repo's agent surface (AGENTS.md / CLAUDE.md / .cursor rules; auto-detected, idempotent, append a marked block) + verifies the tool. So a user adopts by telling their agent *"apply dnr"* → it runs `uvx dnr init`. Inspectable, pinned, touches the repo only.
- **Done when:** an agent given only the skill queries a dnr folder and skips re-parsing correctly; `dnr init` bootstraps from a single user phrase.

## ⬜ M9 — Agent scenario testing & dogfooding
> Drive the whole thing with real agents across many scenarios — the bugs that specs & unit tests miss surface here, and feed M10–M12. This is the real release-readiness gate.
- [ ] **Scenario matrix**, run by agents: ingest / query / read / route / move / edit / re-ingest across diverse inputs — legal PDFs, scanned, audio, mixed folders, huge files, cold folders, stale index, moved/renamed files
- [ ] **Multi-harness**: Claude Code / Codex / Cursor — does each *actually* skip re-parsing given only the skill?
- [ ] **Adversarial / edge scenarios**: malicious record (injection), forged signature, corrupt / encrypted file, concurrent agents, re-encoded transport
- [ ] **Measure**: cache hit-rate · protocol-compliance rate · token / latency delta · a failure taxonomy → backlog for M10 (operability) & M11 (security)
- [ ] Run as **multi-agent workflows** (fan scenarios out in parallel)
- **Done when:** agents complete the scenario matrix with a known failure list + a real hit-rate / savings number (the seed of the M14 benchmark).

## ⬜ M10 — Reversibility & corpus operability
> Make it safe to undo, and runnable at corpus scale.
- [ ] `dnr strip` (un-embed, restore original) · **bulk rollback** of a bad ingest
- [ ] **Resumable / idempotent** ingest after crash · `--dry-run`
- [ ] Rebuild a corrupted/lost `.dnr.db` without re-incurring transcription
- [ ] **Model-upgrade policy**: re-transcribe only lossy methods (asr/ocr/vision), skip `text-extract`; partial/lazy migration; mixed-version coherence
- [ ] Backup/dedup awareness (embedding changes whole_hash → re-backup churn)
- **Done when:** a bad bulk ingest is fully revertible and a crashed run resumes cleanly.

## ⬜ M11 — Security & privacy
> Treat every embedded record as untrusted input; don't leak on share.
- [ ] **Threat-model document** — injection, forgery, TOFU poisoning, share-time exfiltration, chain-of-custody
- [ ] `transcript` wrapped as untrusted data; an injection test corpus
- [ ] **Sensitivity flag** + refuse-embed on confidential/evidentiary; `dnr strip` before sharing
- [ ] Index / FTS / vector poisoning sanitization
- **Done when:** a malicious dnr file cannot steer a consuming agent or pass as trusted.

## ⬜ M12 — Spec formalization (the standard)
> Make it implementable by others, and able to evolve.
- [ ] `spec/dnr-0.1.md` + `dnr.schema.json` (JSON Schema)
- [ ] Carrier mapping table · per-format canonicalization algorithms · conformance vectors
- [ ] Versioning / compatibility rules · profile registry · change-control process (governance seed)
- **Done when:** a second, independent implementation passes the conformance vectors.

## ⬜ M13 — Format expansion & scale hardening
- [ ] Remaining carriers (FLAC / OGG / M4A / MP4·MOV / docx·xlsx / PNG·TIFF)
- [ ] Large-corpus performance · multi-agent stress · recovery primitives at scale

## ⬜ M14 — Release, governance & adoption
> Ship, then earn adoption with **proof** — not cold asks. (See "Adoption strategy" below.)
- [ ] v0.1 public release on GitHub
- [ ] **Benchmark** (the key adoption asset): measured token / latency savings on re-reads + agent protocol-compliance rate (built on M9's numbers)
- [ ] 2-minute demo · one-command try (`uvx dnr …`)
- [ ] **Launch posts** (GeekNews / Show HN) — lead with the demo + benchmark; CTA = the one-phrase bootstrap (`uvx dnr init`). A spike, not a strategy — only after v0.1 + the try-path are frictionless.
- [ ] **Opt-in surfaces first**: MCP server + skill/`AGENTS.md` snippet (users adopt without any maintainer PR)
- [ ] **OKF-compatible sidecar emit** (ride existing rails, don't fight them)
- [ ] **Targeted integrations**: PRs only to projects with a clean plugin/tool extension point — benefit-first, after the benchmark exists
- [ ] Governance: contribution process + spec change control
- **Done when:** ≥1 external project/user adopts via the opt-in surface, with the benchmark as evidence.

---

### Adoption strategy (M14) — why "proof-then-pitch", not cold PRs
1. **Prove first.** Maintainers adopt things that already work + have a number, not specs. Ship → benchmark (token/latency savings) → a few real users → *then* integrate.
2. **Opt-in beats PR.** Consumption is ambient `sqlite3`, so the integration is tiny — and an **MCP server / skill snippet** lets users turn it on with zero maintainer change, sidestepping PR rejection. Reserve real PRs for projects with a plugin/tool registry.
3. **Benefit-first messaging.** Not "adopt my standard" — "your agent re-parses PDFs every turn; drop this in for an N% saving." Show, don't tell.
4. **Target narrowly.** Document-heavy RAG / coding / research agents where re-parsing is a felt pain. 50 drive-by PRs read as spam and cost reputation; a few working, wanted integrations win.

---

*All docs in English (public repo).*
