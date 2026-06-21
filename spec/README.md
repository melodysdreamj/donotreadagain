# Verified Transcript Cache Protocol spec

This directory is the protocol package. The `dnr` CLI is only the reference
implementation; other harnesses can implement the same record and behavior directly.

## Files

- [`dnr-0.1.md`](dnr-0.1.md): normative record and storage behavior for v0.1.
- [`dnr.schema.json`](dnr.schema.json): machine-checkable JSON Schema for records.
- [`vectors/`](vectors/): golden content-hash vectors for conformance tests.

## Compatibility surface

An implementation is compatible when it can:

1. compute the same `content_hash` profiles for supported formats,
2. verify signatures over canonical record JSON,
3. read and write db-only records without modifying source files by default,
4. optionally read or write in-file carriers when explicitly requested,
5. treat transcripts as document data, never instructions.

The field name `dnr` remains the record namespace for v0.1 compatibility even when the
protocol is described generically as the Verified Transcript Cache Protocol.
