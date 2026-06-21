# dnr — settled design Q&A

> **If you are an agent (or person) about to question dnr's design on one of these points: read this first.**
> These doubts were raised, argued, and **settled**. Don't relitigate them — build on them.
> Deeper rationale: [vision.md](vision.md) · roadmap/debt: [MILESTONES.md](MILESTONES.md) · spec: [spec/dnr-0.1.md](spec/dnr-0.1.md).

---

### Q1. Transcribing costs a model pass up front. Isn't this a public-goods problem (producer pays, future readers benefit)?
**No — for the target use case the producer IS the biggest beneficiary.** dnr targets **repeat-access** corpora: legal, research, compliance — where the *same* files are read on *every* query. It is not a crawler that pre-transcribes a folder just because files are pending; it caches the files you already had to read for the current task. If one of those needed files has an empty/garbled/unusable cache, repair that file immediately; ask only before expanding into whole-folder OCR/searchability work. The owner who transcribes once reaps it on every later read (a litigation folder's PDFs get re-read dozens of times). The public-goods worry only bites for *one-off* files, which are not the wedge. → Go after repeat-access verticals first; "universal standard" comes later.

### Q2. Why not embed the transcript *inside the file* by default?
Because harness adoption and evidence safety are more important than maximum portability. In-file records are still useful when a user explicitly wants a transcript to travel inside a copied file, but rewriting original bytes makes many harnesses, legal workflows, backups, and sync tools nervous. The default is therefore conservative: store records in the folder's `.dnr.db`, keep originals byte-identical, and require explicit `--embed` when portability matters more than avoiding file modification.

### Q3. There are **no `.dnr.json` sidecars**. So where do records go?
Three cases, never a sidecar. **(1) db-only by default** — records live in the folder's `.dnr.db`, originals stay byte-identical, and changed files invalidate their stale records on the next scan. This is the harness-friendly default for every format. **(2) Optional in-file** for carrier formats — **PDF → XMP, MP3 → ID3, M4A/MP4/MOV → MP4 freeform atom, FLAC/OGG/OPUS → Vorbis/Opus comments, PNG → iTXt, JPEG → APP segment**. Add `--embed` only when the user explicitly wants portable in-file records. **(3) Nothing at all** for already-readable text (`.txt`/`.md`/`.csv`) — it needs no transcription and no record; an agent just reads it. Making any artifact for plain text is pure overhead, so dnr makes none.

### Q4. `.dnr.db` — what is it, and what's "in-file" vs "db-only"?
- **`.dnr.db`** — the per-folder **index and default record store** (SQLite + FTS5). **One per folder.** It holds db-only records plus harvested copies of optional in-file records. You `dnr query` it. A db-only row is preserved across re-scans while its source file still matches the signed `content_hash`; if the source changes or disappears, the stale row is removed and the file must be re-ingested/re-recorded.
- There is **no `.dnr.json`** anymore — sidecars were removed (Q3).

### Q5. Won't agents simply fail to discover dnr is present (not curious enough to inspect metadata)?
Three layers, weakest to strongest: (a) the **`.dnr.db` shows up in a folder listing** — an agent that lists the folder sees it; (b) **every record self-describes** via an `_about` pointer (and the `.dnr.db` readme), so inspecting any dnr artifact reveals what it is + the skill URL; (c) the real ceiling is **native agent adoption** (Claude Code / Codex / Cursor knowing dnr out of the box). Discovery is a *floor* problem (a/b raise it) with a *ceiling* (c) that is the project's main open risk — and an **adoption** problem, not a technical one. **Never rename original files** to advertise (e.g. `contract.dnr.pdf`) — it breaks references and evidence chains. The signal must never mutate the user's filenames.

### Q6. Should `dnr init` drop a note/manual into each folder?
**Not by default.** Each record self-describes (`_about`), and the `.dnr.db` readme points to the skill. Plain `dnr init` only ensures a signing key. If you explicitly want a repo-level agent hint, run `dnr init --agent-file AGENTS.md` or `dnr init --agent-file CLAUDE.md`; it appends or upgrades the bootstrap and is idempotent. dnr no longer writes global agent instructions; users and harnesses opt in per project or by native integration. The bootstrap includes the exact PyPI package (`donotreadagain`), recommends `pipx install donotreadagain`, and keeps `uvx --from donotreadagain dnr ...` as the one-off fallback so agents should not ask which installer to use.

### Q7. To *read* do I need the skill, and to *transcribe* do I need to install the CLI?
Wrong axis. **Skill = operating instructions** (how to use dnr — covers *both* reading and transcribing; learned once). **dnr CLI = the executor**; recommended install is `pipx install donotreadagain`, with `uvx --from donotreadagain dnr …` as a one-off/fallback path if installing is unavailable. Reading what's already cached can even need *zero* dnr tooling — ambient `sqlite3` reads `.dnr.db`. Transcribing/extracting needs the CLI. Audio ASR is an extra (`pipx inject donotreadagain faster-whisper`, or `donotreadagain[audio]`) and ffmpeg may still be needed for decoding.

### Q8. A signed record is "trusted" — does that mean the transcript is *correct*?
**No. trusted ≠ faithful.** The signature proves **provenance + that the record matches this file**, not that the transcription is accurate (a wrong-but-signed transcript still verifies; e.g. CJK PDF text-extract can drop word spaces, OCR has typos). Fidelity is handled two ways: (a) the skill ships and **evolves best-practice transcription guidance** (the verbatim contract, recommended methods/models); (b) — the stronger lever — **provenance is recorded** (`method` / `transcriber` / `prompt_hash`), so a **consumer applies its own fidelity policy** ("trust frontier-vision transcripts; re-verify CJK text-extract"). So "trusted ≠ faithful" is a **tunable dial**, not a hidden gap — and the skill must teach consumers to read provenance, not just teach producers to transcribe well.

### Q9. Is dnr the OCR/ASR engine?
The Verified Transcript Cache Protocol is a **source-file transcript cache protocol plus cache/trust/index layer**. The transcript is an *input*, produced by whoever is best placed: the calling agent's own vision model (`dnr record`), local extractors (PyMuPDF/pypdf, python-docx, openpyxl), local ASR (faster-whisper), or an API. The protocol owns the *contract* (verbatim guide) and the *trust/provenance* layer; `dnr` is the reference CLI. This keeps it neutral and lets fidelity improve independently (Q8). It is not a general knowledge-base format; it stores faithful text tied back to concrete source files.
