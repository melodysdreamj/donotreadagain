# dnr — Milestones

Build roadmap. Full design → [vision.md](vision.md). &nbsp; Status: ✅ done · 🔜 in progress / next · ⬜ todo

**v0.1 goal —** a working `dnr` that ingests PDF + audio (transcribe → canonical-hash → deterministic embed → sign), builds a per-folder queryable index (Korean/CJK search included), and lets an agent read/query with **no install**. Fundamentals-first: the `content_hash` and signing primitives are *proven* before the rest is layered on.

**Critical path:** M1 → M2 → (M3 ∥ M4) → M5 → M6 → M7 → M8 → M9. &nbsp; **v0.1 cut** = M1–M8 (build) + **M9 (dogfood — the real release-readiness gate)**. &nbsp; **M10–M14** = operability, security, the standard, scale, release.

**Progress (2026-06-20):** working `dnr` package + CLI — `hashing`/`record`(JCS)/`embed`(PDF·mp3·sidecar; gates 1·2·4)/`signing`(Ed25519+keyring); `transcribe` (transcriber-agnostic: local text-extract + agent path + Whisper provider) + `guide` (verbatim contract `dnr-verbatim-1`); `ingest`/`read_cached` (skip-reparse, idempotent); `index` (`.dnr.db` fixed table + FTS5 **trigram for CJK** + incremental scan + move resilience + tombstone). CLI: **keygen·ingest·record·read·verify·guide·types·index·query**. End-to-end (ingest→index→query→read) works with **zero API keys**; `dnr init` installs the agent skill (one-phrase bootstrap); **57 tests green.** **M1–M12 landed.** Then a **broad multi-user dogfood** (11 personas, each in an isolated folder) found 2 ship-blockers the targeted run missed — **both now fixed**: (1) the **index/query trusted UNSIGNED records** (security bypass — `read`/`verify` refused forged records but `query` surfaced them); `scan` now verifies signature + content_hash before harvesting. (2) **duplicate-content PRIMARY-KEY collision** silently dropped a file; rows are now keyed by **path**. Also added `query --list`, "no results"/CJK-short-term hints, and stripped-record removal from the index. **Then the 3 high dogfood items were fixed too:** non-PDF `ingest` (text → `method:none` sidecar, searchable; images/unknown → clean "use `dnr record`" errors, no pypdf crash); **CJK <3-char search** (LIKE substring fallback → 2-char Korean terms 계약/이혼/특허 now match); **spec `content_hash`** now documents the `<CS>`/`<IM>` framing + ships **golden vectors** (`spec/vectors/`, text + audio). **Then format coverage expanded:** **docx** (local python-docx text-extract), **images** (JPEG/PNG/TIFF/WEBP — pixel content_hash + agent `dnr record` + sidecar), and OOXML content_hash; cross-format search verified (docx + image in one folder). **Then a real-corpus dogfood** (the founder's `law-example` — 12 real Korean legal docs) found + fixed 4 more bugs: **macOS NFD paths** (now NFC-normalized in the index), **`start_date` as a real column** (`--where` now consistent with `--sort`), **language auto-detect** (`lang='ko'` now works for local ingest), and **filename-searchable FTS** (terms in the filename now match). Query surface also gained `--tag`, `--sort/--desc`, `--match --context N` (KWIC snippets), `--list`, and `record --tags`. (`#5` Korean-PDF word-spacing is inherent to CJK PDF text layers — not fixable from text; use the vision/`dnr record` path.) **76 tests green**, all 4 fixes verified on the real corpus. Then **sidecars were removed entirely** (`.dnr.json` gone): **images now embed in-file** (PNG iTXt / JPEG APP segment — pixels untouched, content_hash invariant, multi-segment chunking for >64KB), text/docx/etc. store a **db-only** record in `.dnr.db` (authoritative; preserved across re-scans), and `--no-embed` forces db-only for evidentiary originals (file byte-identical). Distribution also moved from a per-folder note to a **fetch-once `SKILL.md`** + each record's `_about` self-pointer. Then a **query-memory** layer landed: **composed queries** (`--match` ∩ `--tag a,b` ∩ `--since/--until` ∩ `--where`, one shot), **saved queries** (`--save`/`dnr queries`/`--use` — stores the *query*, re-runs live so it never goes stale), and **`dnr tag <file> <tag>…`** so an agent accumulates tags as it works (carrier files re-indexed immediately). Remaining debt: golden vectors / cross-tool, proper `dnr:` XMP namespace, more in-file carriers (OOXML for docx, audio containers, video), pre-query auto-scan, ingest lock. **Distribution decided: assume Python 3.10+ (pip/pipx/`uvx --from donotreadagain dnr`) — Python's stdlib `sqlite3` covers the read path, so one dependency does both; a standalone per-platform binary for Python-less environments is deferred post-1.0.** Verified: a clean venv `pip install .` yields a working standalone `dnr` (no source tree), sqlite included.

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

## 🔜 M4 — Transcription (ingest)
> Turn a raw file into a faithful record, once. **dnr owns no model** — the transcript is supplied by the agent or a local provider.
- [x] **Transcriber-agnostic ingest pipeline** — content_hash → transcribe → record → sign → embed
- [x] **Local `text-extract`** (pypdf, born-digital PDF, NFC) · **agent-supplied** path (`dnr record`) · **text files** (.txt/.md/.json/… → `method:none` sidecar) · clean errors for images/unknown
- [ ] Local models: **Whisper** (audio) · local OCR/vision (scans); optional hosted API
- [ ] Method hierarchy enforced: `text-extract` → `vision` → (`ocr` demoted)
- [ ] **Verbatim** transcription contract (prompt) shipped in the skill: complete, no summary, mark uncertainty
- [ ] provenance: version, instruction_id, prompt_hash, confidence; per-segment language tagging (feeds M6)
- [ ] Cost control: query-driven lazy ingest · ask-the-user · `dnr ingest --glob --budget`
- **Done when:** a PDF / audio ingests into a verbatim, signed, embedded record with provenance — agent-supplied or local, no API key required.

## 🔜 M5 — Index (query layer)
> A folder becomes a queryable table — cheaply, incrementally.
- [x] `.dnr.db`: fixed base table + `dnr_fts` (FTS5) + `_dnr_readme`
- [x] Incremental scan: stat → record → harvest; tombstone deletes
- [~] **index ≠ ingest** done; cold-folder media → currently *skipped* (pending-rows TODO)
- [ ] Pre-query incremental scan (`--no-scan` to skip)
- [x] Move resilience: `content_hash` match → update `path` only
- [~] Concurrency: SQLite **WAL** on; `content_hash` ingest lock TODO
- **Done when:** second scan is fast (stat-skips ✅), queries are fresh, moves don't re-transcribe ✅

## 🔜 M6 — i18n & search quality
> Make non-English — especially Korean/CJK — actually searchable (the founder's own corpus).
- [x] **trigram FTS5** + **LIKE substring fallback for <3-char terms** → 2-char Korean (계약/이혼/특허) matches; **filename also searchable** (FTS over name)
- [x] **NFC normalization end-to-end** — index stores NFC paths/names (fixes macOS NFD); text NFC-normalized
- [x] **language auto-detect** (script heuristic) → `lang` set on local ingest; `--where lang='ko'` works
- [~] Multilingual `fields` consistency / RTL / bidi remaining
- **Done when:** ✅ Korean legal-doc search (incl. 2-char terms + filenames) returns correct hits — verified on the real `law-example` corpus

## 🔜 M7 — CLI & distribution
> One tool that ties it together, runnable anywhere.
- [~] `dnr init·ingest·record·read·verify·keygen·guide·types·index·query` done; `seal·strip` TODO
- [x] Protocol enforced in code (`dnr read/index/query` are real commands, not prose)
- [ ] `uvx` package **+ single static binary** (per-platform releases) — dependency-free drop-in
- **Done when:** `uvx dnr index <folder>` and `dnr query` work on a fresh machine, offline (minus transcription API).

## 🔜 M8 — Agent integration (consumer)
> Zero-install consumption by AI agents.
- [x] **agent skill (`SKILL.md`)**: fixed schema + example queries + consumer contract + verbatim guide; a fetchable skill (frontmatter name/description), **not** a per-folder note
- [x] **skill encodes the full decision flow** (A: one file → self-validating `dnr read` / B: folder → status→transcribe→index→query) and was **adversarially tested** — fresh agents given only the skill text + 6 scenarios; judged vs the canonical flow + a doc critic over 4 rounds (3→4→5 correct, **0 wrong throughout**), fixing real gaps (read=self-validating; `--sidecar` mutation; transcribe-as-a-step; bulk-only ask-gate) so the wording matches actual CLI behavior
- [~] Consumer path documented (`dnr read`/`query`; raw `sqlite3` via `_dnr_readme`)
- [x] **transcribe-first ask-flow** — `dnr status <folder>` reports coverage by cost (model = image/audio/video / parse = PDF·Office / cheap = text); the skill tells the agent to run it on the first folder-wide question and **offer to transcribe-first** when expensive files are un-transcribed (one-time pass → every later view is a cache hit). Verified on the real corpus: `status 자료/` → "0/441 transcribed, 92 model + 202 parse pending → transcribe-first recommended".
- [x] **No per-folder note — self-describing + fetch-once skill** — every record carries an `_about` pointer (and the `.dnr.db` readme points to the skill), so an agent that meets a dnr artifact fetches `SKILL.md` **once** (committed at the repo root / `dnr skill`) and then knows dnr in every folder; nothing is written into the user's folders. `dnr init` now only ensures a signing key. Run with no install via `uvx --from donotreadagain dnr`.
- **Done when:** an agent given only the skill queries a dnr folder and skips re-parsing correctly; `dnr init` bootstraps from a single user phrase.

## 🔜 M9 — Agent scenario testing & dogfooding
> Drive the whole thing with real agents across many scenarios — the bugs that specs & unit tests miss surface here, and feed M10–M12. This is the real release-readiness gate.
- [x] **Scenario matrix**, run by agents: cache-hit, cross-file query, cold folder, move, freshness, incremental, CJK, + adversarial
- [~] **Multi-harness**: exercised via the real `dnr` CLI by agents; actual Claude Code / Codex / Cursor runs are a broader TODO
- [x] **Adversarial / edge**: forged-unsigned (refused), tampered-signed (verify fails), freshness (no stale leak), corrupt/garbage file
- [x] **Measure**: 8/10 pass, security held, failure taxonomy + prioritized backlog produced
- [x] Run as a **multi-agent workflow** (10 scenarios in parallel + synthesis)
- **Done when:** ✅ matrix complete with a failure list; fixes fed back (corrupt-file robustness → done). Remaining low-pri: CJK <3-char FTS, file-embedded-cache note.

## 🔜 M10 — Reversibility & corpus operability
> Make it safe to undo, and runnable at corpus scale.
- [x] **Robustness** (from M9 dogfooding): corrupt/missing files no longer crash — clean errors, one bad file never aborts a scan; `dnr read` falls back gracefully
- [x] `dnr strip` (un-embed, in-file + sidecar; content unchanged) · **bulk rollback** TODO
- [ ] **Resumable / idempotent** ingest after crash · `--dry-run`
- [ ] Rebuild a corrupted/lost `.dnr.db` without re-incurring transcription
- [ ] **Model-upgrade policy**: re-transcribe only lossy methods (asr/ocr/vision), skip `text-extract`; partial/lazy migration; mixed-version coherence
- [ ] Backup/dedup awareness (embedding changes whole_hash → re-backup churn)
- **Done when:** a bad bulk ingest is fully revertible and a crashed run resumes cleanly.

## 🔜 M11 — Security & privacy
> Treat every embedded record as untrusted input; don't leak on share.
- [x] **Threat-model document** — `SECURITY.md` (injection, forgery, TOFU, exfiltration, custody) + dogfood evidence
- [~] `transcript` as untrusted data (skill + contract); injection covered by forged/tampered dogfood; dedicated injection corpus TODO
- [~] `dnr strip` before sharing done; sensitivity-flag refuse-embed TODO
- [~] Poisoning surface documented; sanitization helpers TODO
- **Done when:** ✅ dogfooding showed a malicious/forged/tampered file cannot pass as trusted or steer the agent.

## 🔜 M12 — Spec formalization (the standard)  ← the goal
> Make it implementable by others, and able to evolve.
- [x] `spec/dnr-0.1.md` (normative) + `spec/dnr.schema.json` (JSON Schema) + `dnr validate` / `dnr schema`
- [x] Carrier mapping table · per-format canonicalization (incl. documented PDF `<CS>`/`<IM>` framing) · conformance gates (in spec)
- [x] **Golden conformance vectors** — `spec/vectors/` (text + audio) + a test the impl must reproduce; PDF/image/OOXML vectors pending
- [~] Versioning / forward-compat in spec; profile registry, governance = TODO
- **Done when:** a second, independent implementation passes the published vectors (text/audio shipped; PDF vector + a real 2nd impl remain).

## 🔜 M13 — Format expansion & scale hardening
- [~] **docx** (local extract) + **images** JPEG/PNG/TIFF/WEBP (pixel content_hash + sidecar + agent record) done; remaining: FLAC/OGG/M4A/MP4·MOV, xlsx/pptx, in-file image XMP/PNG-iTXt, local Whisper wired
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
