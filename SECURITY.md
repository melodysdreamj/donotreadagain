# dnr — security & threat model

## Reporting a vulnerability

Please report security issues **privately** to **melodysdreamj@gmail.com** — do **not** open a
public issue for vulnerabilities. Include reproduction steps; you'll get an acknowledgement and a
fix timeline. Responsible disclosure is appreciated.

---

dnr stores AI-derived transcripts that agents may *trust instead of re-reading* source files. That
trust is the security surface. Records are db-only by default, with in-file embedding available only
when explicitly requested. This document enumerates the threats and how dnr addresses them.
The trust mechanics were exercised in the M9 dogfooding run (see `MILESTONES.md`); the three
security scenarios all held.

## Trust model in one line

Any cached record is **untrusted by default**. A consumer uses a cached transcript in place of
reading a file **only** when the record's signature verifies against a trusted key **and** the
recomputed `content_hash` matches the file. Everything else falls back to reading the content,
and a transcript is always **data, never instructions**.

The folder **index is part of this boundary**: `dnr index` harvests a record only if it passes
the same gate, so `dnr query` can never surface unsigned / forged / tampered content. *(This
index-path check was added after multi-user dogfooding found the index initially trusted
unsigned records — `read`/`verify` refused them but `query` did not. Now both paths verify.)*

## Threats & mitigations

| # | Threat | Mitigation | Dogfood evidence |
|---|---|---|---|
| 1 | **Forgery** — an attacker writes a record into a file you didn't transcribe | Records are Ed25519-signed; consumers trust only keys in their trust list. An unsigned/untrusted record is refused for skip-reparse. | `forged-unsigned`: forged unsigned record → `dnr read` refused it, served none of the payload. ✅ |
| 2 | **Tampering** — a signed record is edited after signing | The signature is over `JCS(record − sig)`; any change invalidates it. | `tampered-signed`: edited field → `verify` reports `signed&trusted: False`, `read` falls back. ✅ |
| 3 | **Stale cache** — file content changes but the record doesn't | `content_hash` binds the record to the decoded content; a mismatch forces a re-read. | `freshness`: content replaced → old transcript did **not** leak. ✅ |
| 4 | **Indirect prompt injection** — `transcript.text` carries instructions aimed at the consuming LLM | The consumer contract treats the transcript as untrusted **data**; the skill instructs agents to never follow instructions found in a transcript. Untrusted records never reach the trusted path. | covered by #1/#2 (untrusted records refused) |
| 5 | **TOFU poisoning** — a poisoned record is cached on first contact | No unconditional trust-on-first-use: trust requires a verified, trusted signature. Records from untrusted origins are search-only + fall back. | — |
| 6 | **Leakage on share** — sharing a cache or opt-in embedded file leaks the transcript / summary / entities | Default db-only records stay in `.dnr.db`; `dnr strip` removes opt-in embedded records before sharing. Sensitive files SHOULD be reviewed before leaving the trust boundary. | `strip` implemented + tested |
| 7 | **Chain-of-custody** — embedding mutates an original evidence file | Original files stay byte-identical by default because records go to `.dnr.db`; optional `--embed` uses atomic temp+rename and should be avoided for evidentiary originals unless explicitly approved. | — |
| 8 | **Index/FTS poisoning** — malicious transcript text steers retrieval | The index is derived and regenerable; query results are paths to verify, not actions. Treat retrieved text as untrusted (same as #4). | — |

## Non-goals / honest limits

- dnr does **not** protect against a compromised local machine or a malicious holder of your
  signing key.
- Verifying faithfulness ("the transcript truly represents the content") is bounded by the
  transcriber; `provenance.method` + `confidence` expose the risk, and high-stakes use SHOULD
  re-derive or cross-check (vision.md §8).
- A `read` re-opens and re-hashes the source. A missing/corrupt source falls back cleanly
  (no crash) rather than serving stale cached text.

## Reporting

This is an early-stage project. Report security issues via a private channel to the maintainer
rather than a public issue.
