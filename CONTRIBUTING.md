# Contributing to dnr

Thanks for your interest! dnr is a small, principled codebase — a quick read of the principles below will save you (and a reviewer) time.

## Getting started

```bash
git clone https://github.com/donotreadagain/donotreadagain
cd donotreadagain
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                 # should be green in ~1s
```

Requires Python 3.10+. No API keys, no network, no services — the whole suite runs locally.

## Project layout

```
src/dnr/
  hashing.py     content_hash (per-format, over DECODED content) + whole_hash
  record.py      build the record + RFC 8785 (JCS) canonicalization
  signing.py     Ed25519 sign / verify; keyring.py manages the local key
  embed.py       carriers — read/write the record into a file's slot (PDF/MP3/PNG/JPEG)
  ingest.py      transcribe → record → sign → store; read_cached (the skip-reparse gate)
  transcribe.py  local providers (pypdf, Whisper, python-docx) + quality/lang heuristics
  index.py       per-folder .dnr.db (SQLite + FTS5): scan/harvest, query, query memory
  guide.py       the verbatim transcription contract; skill.py / bootstrap.py: distribution
  cli.py         the `dnr` command-line surface
spec/            the normative spec + JSON Schema + golden vectors
tests/           pytest; fast, hermetic
SKILL.md         the agent skill (generated from skill.py via `dnr skill`)
```

## Design principles (please don't break these)

1. **dnr is a deterministic substrate; the agent is the intelligence.** dnr does verifiable, repeatable primitives (hash, sign, full-text/structured query). It must **never *infer* metadata** (dates, case numbers, parties, topics) or do fuzzy/semantic search — that's the calling agent's job. Metadata is set *explicitly* (`dnr tag`, `dnr date`).
2. **dnr owns no model.** The transcript is an *input*, produced by the agent (vision), a local model (Whisper, text-extract), or an API. Don't add a hard model dependency to the core.
3. **File = canonical truth; the index is a regenerable cache.** Anything in `.dnr.db` (except authoritative db-only records) must be reconstructable from the files.
4. **Determinism is load-bearing.** `content_hash` must stay invariant when the record is embedded, and re-embedding identical content must be byte-stable. New carriers must preserve this (see below). No timestamps in records/embeds.
5. **`trusted ≠ faithful`.** Signing proves provenance + file-match, not transcription accuracy. Don't conflate them; surface quality, don't fake it.
6. **No sidecar files, no per-folder notes.** Records live in-file or db-only; discovery rides on the artifacts' self-description.

If a change rubs against one of these, say so in the PR — sometimes the principle should evolve, but it should be a conscious decision (see [qna.md](qna.md) for ones already settled).

## Adding a format carrier (common contribution)

To make a new format embed *in-file* (instead of db-only):

1. Add `embed_<fmt>` / `extract_<fmt>` / `strip_<fmt>` in `embed.py`, register them in `_EMBED`/`_EXTRACT`/`_STRIP`.
2. **Critical:** embedding must NOT change the file's *decoded content* — `hashing.content_hash` must be invariant before/after embed (e.g. for JPEG, insert a metadata segment without re-encoding the pixels). Re-embedding identical input must be byte-stable.
3. Update `formats.py` (`SUPPORTED`) and add a test asserting: round-trip, `content_hash` invariance, idempotent re-embed, and `strip`.

## Tests

- Every change needs a test. The suite is the contract — keep it green and fast (no network, no large fixtures).
- Use `tmp_path` and set `DNR_HOME` to an isolated dir (see the fixtures in `tests/`).
- Run `pytest` before opening a PR.

## Pull requests

- Branch from `main`; keep PRs focused.
- Conventional-ish commit subjects: `feat(dnr): …`, `fix(dnr): …`, `test: …`, `docs: …`.
- If you changed agent-facing behavior, regenerate `SKILL.md` (`dnr skill > SKILL.md`) and update it.
- Describe *what* and *why*; link any relevant `qna.md` / spec section.

## Reporting bugs / ideas

Open an issue (templates provided). For anything security-sensitive, see [SECURITY.md](SECURITY.md) — don't file a public issue for vulnerabilities.

By contributing you agree your work is licensed under the project's [MIT License](LICENSE).
