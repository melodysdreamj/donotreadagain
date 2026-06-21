# dnr — settled design Q&A

> **If you are an agent (or person) about to question dnr's design on one of these points: read this first.**
> These doubts were raised, argued, and **settled**. Don't relitigate them — build on them.
> Deeper rationale: [vision.md](vision.md) · roadmap/debt: [MILESTONES.md](MILESTONES.md) · spec: [spec/dnr-0.1.md](spec/dnr-0.1.md).

---

### Q1. Transcribing costs a model pass up front. Isn't this a public-goods problem (producer pays, future readers benefit)?
**No — for the target use case the producer IS the biggest beneficiary.** dnr targets **repeat-access** corpora: legal, research, compliance — where the *same* files are read on *every* query. The owner who transcribes once reaps it on every later read (a litigation folder's PDFs get re-read dozens of times). The public-goods worry only bites for *one-off* files, which are not the wedge. → Go after repeat-access verticals first; "universal standard" comes later.

### Q2. Why embed the transcript *inside the file*? Wouldn't a sidecar or a per-folder index be simpler and less fragile?
**Because in-file survives reorganization.** Real folders are messy and multi-layered: files get exported into court bundles, emailed, copied into subfolders, reorganized by other tools. If the transcript lives in the file, it travels with the content through all of that — move/rename/copy/email and it's still there; you can `dnr index <any-subfolder>` and re-harvest with **no re-transcription**. The `.dnr.db` index is per-folder and regenerable, so it never *is* the truth — only the in-file record is. The embed complexity (deterministic re-embed, pixels untouched) is real, but the portability payoff justifies it. → **In-file is the default for any format with a metadata slot.**

### Q3. There are **no `.dnr.json` sidecars**. So where do records go?
Three cases, never a sidecar. **(1) In-file** for carrier formats — **PDF → XMP, MP3 → ID3, PNG → iTXt, JPEG → APP segment** (pixels untouched, `content_hash` invariant; portable). **(2) db-only** for non-carrier formats that still need transcription (docx, …, and anything via `--no-embed`) — stored in that folder's `.dnr.db`; not portable (folder-scoped), the accepted tradeoff for a format with no slot or an evidentiary original you must not modify. **(3) Nothing at all** for already-readable text (`.txt`/`.md`/`.csv`) — it needs no transcription and no record; an agent just reads it. Making any artifact for plain text is pure overhead, so dnr makes none. Adding more in-file carriers (OOXML for docx, audio containers, video) is planned debt — until then those are db-only.

### Q4. `.dnr.db` — what is it, and what's "in-file" vs "db-only"?
- **`.dnr.db`** — the per-folder **index** (SQLite + FTS5). **One per folder.** It holds two kinds of rows: **harvested** copies of in-file records (regenerable cache; the file is the truth), and **db-only** records (authoritative — the only copy, for formats with no carrier or `--no-embed`). You `dnr query` it. A db-only row is preserved across re-scans while its source file still matches the signed `content_hash`; if the source changes or disappears, the stale row is removed and the file must be re-ingested/re-recorded.
- There is **no `.dnr.json`** anymore — sidecars were removed (Q3).

### Q5. Won't agents simply fail to discover dnr is present (not curious enough to inspect metadata)?
Three layers, weakest to strongest: (a) the **`.dnr.db` shows up in a folder listing** — an agent that lists the folder sees it; (b) **every record self-describes** via an `_about` pointer (and the `.dnr.db` readme), so inspecting any dnr artifact reveals what it is + the skill URL; (c) the real ceiling is **native agent adoption** (Claude Code / Codex / Cursor knowing dnr out of the box). Discovery is a *floor* problem (a/b raise it) with a *ceiling* (c) that is the project's main open risk — and an **adoption** problem, not a technical one. **Never rename original files** to advertise (e.g. `contract.dnr.pdf`) — it breaks references and evidence chains. The signal must never mutate the user's filenames.

### Q6. Should `dnr init` drop a note/manual into each folder?
**Not by default.** Each file self-describes (`_about`); an agent fetches the skill (`SKILL.md`) **once** from the canonical URL and then knows dnr in *every* folder. Plain `dnr init` only ensures a signing key. If you explicitly want a repo-level agent hint, run `dnr init --agent-file AGENTS.md` or `dnr init --agent-file CLAUDE.md`; it appends or upgrades the bootstrap and is idempotent. For a persistent all-project habit, run `dnr init --global-agent`; the skill tells agents to do this on first use when supported. The bootstrap includes the exact PyPI package (`donotreadagain`) and preferred runner (`uvx --from donotreadagain dnr`) so agents should not ask which installer to use.

### Q7. To *read* do I need the skill, and to *transcribe* do I need to install the CLI?
Wrong axis. **Skill = knowledge** (how to use dnr — covers *both* reading and transcribing; learned once). **dnr CLI = the executor**, run with **no install** via `uvx --from donotreadagain dnr …`. Reading what's already cached can even need *zero* dnr tooling — ambient `sqlite3` reads `.dnr.db`, `exiftool` reads the record. Transcribing needs the CLI (still via uvx). A persistent install is optional, only for heavy use.

### Q8. A signed record is "trusted" — does that mean the transcript is *correct*?
**No. trusted ≠ faithful.** The signature proves **provenance + that the record matches this file**, not that the transcription is accurate (a wrong-but-signed transcript still verifies; e.g. CJK PDF text-extract can drop word spaces, OCR has typos). Fidelity is handled two ways: (a) the skill ships and **evolves best-practice transcription guidance** (the verbatim contract, recommended methods/models); (b) — the stronger lever — **provenance is recorded** (`method` / `transcriber` / `prompt_hash`), so a **consumer applies its own fidelity policy** ("trust frontier-vision transcripts; re-verify CJK text-extract"). So "trusted ≠ faithful" is a **tunable dial**, not a hidden gap — and the skill must teach consumers to read provenance, not just teach producers to transcribe well.

### Q9. Should dnr ship its own transcription model?
**No.** dnr is a **protocol/format**, transcriber-agnostic. The transcript is an *input*, produced by whoever is best placed: the calling agent's own vision model (`dnr record`), a local model (Whisper, text-extract), or an API. dnr owns the *contract* (verbatim guide) and the *trust/provenance* layer, not a model. This keeps it neutral and lets fidelity improve independently (Q8).
