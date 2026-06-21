# dnr record format — specification v0.1 (draft)

Status: **draft**. Rationale and the broader vision live in [`../vision.md`](../vision.md); this
document is the normative contract. The machine-checkable record schema is
[`dnr.schema.json`](dnr.schema.json).

The key words MUST, MUST NOT, SHOULD, MAY are to be interpreted as in RFC 2119.

---

## 1. Scope

dnr makes an expensive-to-parse file *self-describing*: a single, signed JSON **record** —
holding a faithful **transcript** plus provenance and queryable fields — is embedded in the
file's own native metadata slot when the format has one. For formats without a carrier, or
for originals that must remain byte-identical, the record is stored db-only in the folder's
`.dnr.db`. Consumers read the cached transcript instead of re-parsing. A regenerable
per-folder index makes a folder queryable.

In scope: PDF, audio (mp3/wav/…), images, video, office documents. Out of scope: plain-text
formats (txt/csv/json — already cheap to read; no metadata slot), and files that must not be
mutated (digitally signed, read-only) — those use db-only storage or are excluded.

## 2. The record

A record is a JSON object conforming to [`dnr.schema.json`](dnr.schema.json). Required members:
`dnr` (MUST equal `"0.1"`), `content_hash`, `source`. Notable members:

| member | meaning |
|---|---|
| `dnr` | spec version + presence marker |
| `content_hash` | `sha256:<hex>` of the **decoded content** (§4) — identity + invalidation key |
| `source` | `{mime, bytes?, pages?}` |
| `transcript` | `{format, lang?, text, segments?}` — verbatim & complete (§5) |
| `provenance` | `{method, transcriber, instruction_id?, prompt_hash?, version?, confidence?, …}` (§5) |
| `fields` | queryable domain columns (`title`, `summary`, `tags`, `start_date`, …) |
| `extras` | format-specific byproducts |
| `sig` | `{alg, key_id, value}` — signature over the record (§6) |

A record MUST NOT contain the file's path or whole-file hash; those are index-only.
Consumers MUST preserve members they do not understand (forward compatibility).

The record is serialized for hashing/signing with **RFC 8785 (JCS)** canonical JSON, with the
`sig` member removed. All text MUST be Unicode NFC.

## 3. Carrier mapping (where the record lives)

The same JSON is stored as a string in one slot per format:

| format | slot |
|---|---|
| PDF · JPEG · PNG · TIFF · MP4/MOV | XMP, namespace `dnr`, property `dnr:record` *(v0.1 interim: `dc:description`)* |
| MP3 | ID3v2 `TXXX` frame, description `dnr` |
| FLAC · OGG | Vorbis comment `DNR` |
| M4A | MP4 atom |
| docx · xlsx · pptx | OOXML custom XML part |
| no slot / unwritable / oversized / sensitive | db-only record in the folder `.dnr.db` |

A consumer MUST read the same logical record regardless of carrier. When both an embedded
record and a db-only record exist for the same path, the embedded record takes precedence.
There are no `.dnr.json` sidecars in v0.1.

## 4. `content_hash` — per-format canonical (decoded content)

`content_hash` MUST be computed over the file's **decoded content**, never raw container bytes
(raw bytes are not stable across re-serialization). Algorithm: SHA-256, prefixed `sha256:`.

- **PDF** (`dnr-pdf-content-1`) — `sha256` over, for each page in document order: the literal
  ASCII bytes `<CS>` then the decompressed bytes of each content stream; then, for each image
  XObject in the page's resources (XObject keys sorted as strings), the literal ASCII bytes
  `<IM>` then the XObject's decoded stream bytes. `<CS>`/`<IM>` are domain separators.
  Embedding MUST NOT re-encode content/image streams.
- **Audio** (`dnr-audio-1`) — `sha256` of the MPEG audio frames (mp3: excluding ID3v2 prefix
  and any ID3v1 suffix) or the RIFF `data` chunk (wav).
- **Text** (`dnr-text-1`) — `sha256` of the NFC-normalized UTF-8 text (plain-text files have no
  metadata region to exclude).
- **Image** — `sha256` of decoded pixels + dimensions. *(planned)*
- **OOXML** — `sha256` of a sorted manifest of `(member-path, hash-of-decompressed-member)`,
  excluding the dnr part. *(planned)*

Each profile has a name; hashes compare only within a profile. **Golden test vectors** are
published in [`vectors/`](vectors/) (text + audio for v0.1; PDF/image/OOXML pending) — an
independent implementation MUST reproduce them. Embedding a record MUST NOT change
`content_hash` (gate 1, §8).

## 5. Transcription

`transcript.text` MUST be a verbatim, complete rendering of the content — no summarizing,
paraphrasing, omission, or alteration. A separate lossy summary, if any, goes in
`fields.summary`. Implementations follow the **verbatim guide** (`dnr guide`, id
`dnr-verbatim-1`); when an agent/model produced the transcript, `provenance.instruction_id` and
`provenance.prompt_hash` MUST record the guide followed, so verbatim-compliance is auditable.

dnr defines no model. The transcript is supplied by the calling agent, a local model
(Whisper / text-extract / OCR), or an API; `provenance.method` records which
(`text-extract` | `vision` | `ocr` | `asr` | `none`).

## 6. Signing & trust

The record MUST be signed: `sig.value` = Ed25519 signature over `JCS(record − sig)`;
`sig.key_id` identifies the public key. A consumer MUST treat an embedded record as **untrusted**
unless: (a) `sig` verifies against a key in the consumer's trust list, **and** (b) the
recomputed `content_hash` matches the file. Only then MAY the consumer use the transcript in
place of reading the file. Otherwise the record MAY feed search/index but the consumer MUST
fall back to reading the content, and MUST NOT treat `transcript.text` as instructions.

## 7. Consumer contract & index

- **Read**: verify (§6) → use transcript, else fall back. Absence of a record MUST behave
  exactly as today (no regression).
- **Index**: a folder MAY be harvested into `.dnr.db` (SQLite). The table `dnr` MUST exist with
  the fixed columns `content_hash, path, mime, bytes, mtime, indexed_at, method, transcriber,
  version, lang, title, summary, tags, transcript, fields, extras` and a `dnr_fts` FTS5 table,
  so an agent can query without introspection. Harvested in-file records are regenerable from
  the files. db-only rows are authoritative for formats without an in-file carrier and MUST be
  invalidated when the source file no longer matches their `content_hash`. Indexing harvests
  or validates existing records only (it MUST NOT transcribe).

## 8. Conformance gates

A conforming embedder MUST, per carrier, pass:

1. **content_hash invariant** — `content_hash` unchanged after `embed(record)`.
2. **native tags preserved** — pre-existing metadata survives the write.
3. **atomic write** — temp + fsync + rename; never mutate the original in place.
4. **deterministic** — re-embedding the same record is byte-identical (no whole-file-hash drift).

(Gates 1, 2, 4 are validated for PDF/mp3 in this implementation's test suite; see
`../MILESTONES.md`.)
