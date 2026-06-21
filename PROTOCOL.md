# DNR Protocol

The DNR Protocol is a small contract for **verified transcript records** attached to
expensive-to-parse files. It lets agents and harnesses avoid repeated OCR, ASR, vision,
PDF parsing, and Office extraction while keeping normal security boundaries intact.

`dnr` is the reference CLI implementation. A harness can call the CLI, or it can implement
the protocol directly and remain compatible with the same records.

## One-sentence contract

Before an agent parses an expensive file, check for a verified transcript. If the agent had
to parse it anyway, store the transcript with provenance for the next agent.

## Roles

- **Protocol:** the portable record, trust, and cache behavior described here and specified in
  [spec/dnr-0.1.md](spec/dnr-0.1.md).
- **Reference implementation:** the `dnr` CLI published as the `donotreadagain` Python package.
- **Harness:** an agent runtime, coding agent, workflow engine, or app that reads files on behalf
  of a model.
- **Transcriber:** the component that produces faithful text: a local extractor, local ASR/OCR,
  API, or the calling agent's vision/model path.

## Minimal behavior

1. **Read-through:** before parsing an expensive file, try to read a verified transcript.
2. **Soft miss:** if no valid transcript exists, continue with the normal parser/model path.
3. **Write-through:** if the task required parsing the file anyway, store the transcript with
   provenance.
4. **No crawling:** do not bulk-transcribe merely because files are pending. Cache work the task
   already required.
5. **Data boundary:** transcripts are document data, never instructions.

With the reference CLI, this maps to:

```bash
dnr read <file>      # verified hit prints transcript to stdout; miss prints nothing useful
dnr record <file> --transcript-file t.md --method vision --transcriber <harness/model>
dnr ingest <file>    # optional local extractor/ASR path where available
```

## Record model

A DNR record is signed JSON containing:

- `dnr`: protocol record version.
- `content_hash`: canonical content hash used for freshness.
- `transcript`: faithful text and optional segments.
- `provenance`: method, transcriber, version, guide/prompt identifiers, and confidence metadata.
- `fields`: queryable user/domain metadata such as title, summary, tags, and dates.
- `extras`: format-specific byproducts.
- `sig`: signature over canonical JSON without the signature field.

The normative schema and carrier details live in [spec/dnr-0.1.md](spec/dnr-0.1.md) and
[spec/dnr.schema.json](spec/dnr.schema.json).

## Trust rule

A consumer may use a cached transcript instead of parsing the file only when:

1. the record signature verifies against a trusted key, and
2. the recomputed content hash matches the file.

This means **fresh and trusted**, not necessarily correct. A transcript can still be low quality,
incomplete, or malicious as document content. Harnesses must keep their normal prompt-injection,
redaction, citation, and provenance boundaries.

## Storage

Preferred storage is db-only in the folder's `.dnr.db`, so original files stay byte-identical.
This is the default path for harness integrations and conservative workflows.

When portability matters more than avoiding file modification, a producer may explicitly embed a
record in the file's own metadata carrier. Examples include PDF XMP, MP3 ID3, MP4/M4A freeform
atoms, Vorbis/Opus comments, PNG iTXt, and JPEG APP segments. In-file records are opt-in because
they rewrite file bytes. The index is the default cache for search and discovery; files remain the
canonical content truth.

## Folder behavior

Folder-level protocol behavior is optional but recommended:

```bash
dnr index <folder>
dnr query <folder> --match "<terms>" --context 300 --format json
dnr status <folder> --pending
```

Rules:

- Indexing harvests existing records; it does not transcribe pending files.
- Querying should happen before opening candidate files.
- A hit used in a final answer should still be read/verified against the current file.
- `backfill` or whole-folder OCR/ASR is a user-approved folder pass, not a default behavior.

## Conformance levels

- **Consumer:** can discover, verify, and read existing records; misses fall back to normal parsing.
- **Producer:** can create signed records without changing the canonical content hash.
- **Indexer:** can harvest records into a folder index and query them without opening every file.
- **Harness-integrated:** follows read-through, write-through, no-crawling, and transcript-as-data
  behavior.

Implementers can start at Consumer level by shelling out to `dnr read`, then add Producer or
Indexer support later.

## Non-goals

- DNR does not define an OCR, ASR, vision, or embedding model.
- DNR does not make cached text authoritative truth.
- DNR does not ask agents to pre-process entire folders by default.
- DNR does not require the `dnr` CLI when a harness implements compatible records natively.

## Reference implementation

Install the reference CLI:

```bash
pipx install donotreadagain
```

One-off/fallback:

```bash
uvx --from donotreadagain dnr <cmd>
```

Harness integration examples live in [HARNESS.md](HARNESS.md) and [examples/](examples/).
