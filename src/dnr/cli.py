"""dnr command-line interface (M7).

Implemented: keygen · ingest · record · read · verify · guide · types.
Coming (M5/M7): index · query · init · seal · strip.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _cmd_keygen(args) -> int:
    from . import keyring, signing

    _, pub = keyring.default_keypair()
    print(f"default key ready: key_id={signing.key_id(pub)}  ({keyring.home() / 'keys'})")
    return 0


def _cmd_ingest(args) -> int:
    from . import ingest

    rec = ingest.ingest(args.file, transcriber=args.transcriber, sidecar=args.sidecar, force=args.force)
    p = rec["provenance"]
    print(f"ingested {args.file}")
    print(f"  method={p['method']} transcriber={p['transcriber']}")
    print(f"  {rec['content_hash']}")
    if "sig" in rec:
        print(f"  signed key_id={rec['sig']['key_id']}")
    return 0


def _cmd_record(args) -> int:
    from . import ingest

    text = Path(args.transcript_file).read_text(encoding="utf-8") if args.transcript_file else args.transcript
    if text is None:
        print("dnr record: provide --transcript or --transcript-file", file=sys.stderr)
        return 2
    rec = ingest.record_supplied(args.file, text, args.method, args.transcriber,
                                 lang=args.lang, sidecar=args.sidecar)
    print(f"recorded {args.file}: method={args.method} {rec['content_hash']}")
    return 0


def _cmd_read(args) -> int:
    from . import ingest

    text = ingest.read_cached(args.file)
    if text is None:
        print(f"[dnr] no valid cached record for {args.file} — read it normally", file=sys.stderr)
        return 0
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_verify(args) -> int:
    from . import embed, hashing, keyring, signing

    rec = embed.extract(args.file)
    if rec is None:
        print("no dnr record")
        return 1
    trusted = signing.verify(rec, keyring.default_trust())
    try:
        match = rec.get("content_hash") == hashing.content_hash(args.file)
    except ValueError:
        match = None
    print(f"record: yes · signed&trusted: {trusted} · content_hash match: {match}")
    return 0 if (trusted and match) else 1


def _cmd_guide(args) -> int:
    from . import guide

    sys.stdout.write(guide.GUIDE)
    print(f"\n# instruction_id: {guide.INSTRUCTION_ID}")
    print(f"# prompt_hash:   {guide.prompt_hash()}")
    return 0


def _cmd_types(args) -> int:
    from . import formats

    print(formats.render())
    return 0


def _cmd_index(args) -> int:
    from . import index

    s = index.scan(args.folder)
    print(f"indexed {args.folder}: +{s['indexed']} new, {s['skipped']} skipped, "
          f"{s['removed']} removed, {s['untrusted']} untrusted, {s['errored']} errored")
    return 0


def _cmd_query(args) -> int:
    from . import index

    if args.list:
        rows = index.list_all(args.folder)
        for r in rows:
            print(f"{r['path']}\t{r.get('method') or ''}\t{r.get('title') or ''}".rstrip())
        if not rows:
            print("[dnr] index is empty (run `dnr index <folder>`)", file=sys.stderr)
        return 0
    if args.match:
        hits = index.query_match(args.folder, args.match)
        for p in hits:
            print(p)
        if not hits:
            print(f"[dnr] no matches for {args.match!r}", file=sys.stderr)
        return 0
    if args.where:
        rows = index.query_where(args.folder, args.where)
        for r in rows:
            print(r["path"] + (f"\t{r['title']}" if r.get("title") else ""))
        if not rows:
            print("[dnr] no rows match", file=sys.stderr)
        return 0
    print("dnr query: provide --match TEXT, --where SQL, or --list", file=sys.stderr)
    return 2


def _cmd_strip(args) -> int:
    from . import embed

    if embed.strip(args.file):
        print(f"stripped dnr record from {args.file}")
        return 0
    print(f"no dnr record in {args.file}", file=sys.stderr)
    return 1


def _cmd_validate(args) -> int:
    from . import embed, schema

    rec = embed.extract(args.file)
    if rec is None:
        print("no dnr record")
        return 1
    errors = schema.validate(rec)
    if errors:
        print("invalid dnr record:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("valid dnr record (dnr-0.1)")
    return 0


def _cmd_schema(args) -> int:
    import json

    from . import schema

    print(json.dumps(schema.SCHEMA, indent=2, ensure_ascii=False))
    return 0


def _cmd_init(args) -> int:
    import re

    from . import keyring, signing, skill

    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    block = skill.stanza()
    candidates = [target / "AGENTS.md", target / "CLAUDE.md"]
    surfaces = [c for c in candidates if c.exists()] or [target / "AGENTS.md"]
    for f in surfaces:
        text = f.read_text(encoding="utf-8") if f.exists() else ""
        if skill.BEGIN in text and skill.END in text:
            pat = re.escape(skill.BEGIN) + r".*?" + re.escape(skill.END)
            new = re.sub(pat, lambda _m: block, text, flags=re.S)
        else:
            sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
            new = f"{text}{sep}{block}\n"
        f.write_text(new, encoding="utf-8")
    _, pub = keyring.default_keypair()
    print(f"dnr initialized in {target}: skill -> {', '.join(s.name for s in surfaces)}; "
          f"signing key_id={signing.key_id(pub)}")
    print('tell your agent: "apply dnr" (it will read the stanza).')
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dnr", description="Read once, never again.")
    p.add_argument("-V", "--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("keygen", help="create/show the local signing key").set_defaults(fn=_cmd_keygen)

    pi = sub.add_parser("ingest", help="transcribe (local, auto by type) + record + sign + embed")
    pi.add_argument("file")
    pi.add_argument("--transcriber", default=None, help="override the local provider (text-extract, whisper)")
    pi.add_argument("--sidecar", action="store_true")
    pi.add_argument("--force", action="store_true", help="re-ingest even if a valid record exists")
    pi.set_defaults(fn=_cmd_ingest)

    pr = sub.add_parser("record", help="record an agent-supplied transcript (follows the verbatim guide)")
    pr.add_argument("file")
    pr.add_argument("--transcript")
    pr.add_argument("--transcript-file")
    pr.add_argument("--method", default="vision")
    pr.add_argument("--transcriber", default="agent")
    pr.add_argument("--lang")
    pr.add_argument("--sidecar", action="store_true")
    pr.set_defaults(fn=_cmd_record)

    prd = sub.add_parser("read", help="print the cached transcript if trusted, else fall back")
    prd.add_argument("file")
    prd.set_defaults(fn=_cmd_read)

    pv = sub.add_parser("verify", help="check a file's dnr record")
    pv.add_argument("file")
    pv.set_defaults(fn=_cmd_verify)

    sub.add_parser("guide", help="print the verbatim transcription guide (for the agent)").set_defaults(fn=_cmd_guide)
    sub.add_parser("types", help="list supported file types + transcription methods").set_defaults(fn=_cmd_types)

    pix = sub.add_parser("index", help="harvest a folder's records into .dnr.db")
    pix.add_argument("folder")
    pix.set_defaults(fn=_cmd_index)

    pq = sub.add_parser("query", help="query a folder's index")
    pq.add_argument("folder")
    pq.add_argument("--match", help="full-text search (FTS5 trigram; terms 3+ chars)")
    pq.add_argument("--where", help="SQL WHERE over the fixed columns")
    pq.add_argument("--list", action="store_true", help="list every indexed record")
    pq.set_defaults(fn=_cmd_query)

    pin = sub.add_parser("init", help="install the dnr agent skill into this repo + ensure a key")
    pin.add_argument("dir", nargs="?", default=".")
    pin.set_defaults(fn=_cmd_init)

    ps = sub.add_parser("strip", help="remove the dnr record (in-file + sidecar) before sharing")
    ps.add_argument("file")
    ps.set_defaults(fn=_cmd_strip)

    pval = sub.add_parser("validate", help="validate a file's record against the dnr-0.1 schema")
    pval.add_argument("file")
    pval.set_defaults(fn=_cmd_validate)

    sub.add_parser("schema", help="print the dnr record JSON Schema").set_defaults(fn=_cmd_schema)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "fn", None):
        _build_parser().print_help()
        return 0
    try:
        return args.fn(args)
    except Exception as exc:  # clean error, never a raw traceback
        print(f"dnr {getattr(args, 'cmd', '') or ''}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
