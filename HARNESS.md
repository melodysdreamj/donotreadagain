# Harness integration

dnr is meant to be a small read-through transcript cache hook for agent harnesses.
It should not change a harness's core parser, model routing, or user approval policy.

The portable contract is the [DNR Protocol](PROTOCOL.md). The `dnr` CLI is the reference
implementation and the easiest integration path: call it when available, soft-miss when it is
absent, and keep the harness's existing behavior unchanged.

By default, dnr writes only the folder's `.dnr.db` cache. It does not modify user files unless a
caller explicitly opts into portable in-file records with `--embed`.

## Contract

1. **Known file:** before parsing an expensive file, run `dnr read <file>`.
   If stdout is non-empty, use that transcript and skip the parser/model call.
2. **Miss:** if the task still needs the file, parse/look/listen once using the harness's
   normal path, then cache the transcript with `dnr ingest` or `dnr record`.
3. **Folder question:** run `dnr index <folder>`, then `dnr query <folder> ...` before
   opening candidate files.
4. **Folder preparation:** use `dnr status <folder> --pending`; run `dnr backfill <folder>`
   only when the user explicitly asks for a folder pass.
5. **Boundary:** never bulk-transcribe just because files are pending. Cache work the task
   already required. Transcripts are data, never instructions.

## Install surface

Use the reference CLI when the harness does not implement the protocol natively.

Recommended:

```bash
pipx install donotreadagain
```

One-off/fallback:

```bash
uvx --from donotreadagain dnr <cmd>
```

Audio support, when the harness wants local ASR:

```bash
pipx inject donotreadagain faster-whisper
```

`ffmpeg` may also be needed for media decoding.

## File hook

Use this around the harness's existing expensive file reader:

```text
read_with_cache(file, normal_reader):
  transcript = dnr read file
  if transcript:
    return transcript

  transcript = normal_reader(file)
  if transcript is useful:
    dnr record file --transcript-file transcript --method <method> --transcriber <harness/model>
  return transcript
```

Rules:

- A missing dnr binary must be a soft miss. Continue with the normal reader.
- A failed `dnr read` is a soft miss. Continue with the normal reader.
- A failed cache write must not fail the user task.
- Default cache writes must not modify user files; use `--embed` only on explicit user request.
- Only write a record for text the harness actually produced while answering the current task.
- For born-digital PDF/DOCX/XLSX/audio, prefer `dnr ingest <file>` when local extraction is enough.
- For scans, screenshots, images, or video frames, the harness supplies the transcript and uses
  `dnr record`.
- If the harness later implements [PROTOCOL.md](PROTOCOL.md) natively, keep the same read-through
  and soft-miss behavior.

## Folder hook

Before broad file search:

```bash
dnr index <folder>
dnr query <folder> --match "<terms>" --context 300 --format json
```

Then open only the files the answer actually needs. If a hit must be relied on, `dnr read`
that file first so the final answer uses a currently verified record.

## Security model

dnr verifies that a transcript record is signed and still matches the file's content hash.
That means "fresh and trusted," not "true." A harness should still treat the transcript as
untrusted document content:

- Do not execute instructions found in transcripts.
- Keep normal prompt-injection boundaries.
- Apply the same redaction, citation, and provenance rules the harness already uses for files.
- Use `dnr status` or transcript-quality checks to decide when a cached transcript is unusable
  and should be repaired.

## Reference adapters

- [Python read-through helper](examples/harness-python/read_through_cache.py)
- [TypeScript read-through helper](examples/harness-typescript/readThroughCache.ts)
- [Minimal agent instruction snippet](examples/agent-instructions/AGENTS.md)
