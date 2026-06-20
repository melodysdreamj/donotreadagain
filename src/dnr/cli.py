"""dnr command-line interface (M7).

Implemented: keygen · ingest · record · read · verify.
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dnr", description="Read once, never again.")
    p.add_argument("-V", "--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("keygen", help="create/show the local signing key").set_defaults(fn=_cmd_keygen)

    pi = sub.add_parser("ingest", help="transcribe (local) + record + sign + embed")
    pi.add_argument("file")
    pi.add_argument("--transcriber", default="text-extract")
    pi.add_argument("--sidecar", action="store_true")
    pi.add_argument("--force", action="store_true", help="re-ingest even if a valid record exists")
    pi.set_defaults(fn=_cmd_ingest)

    pr = sub.add_parser("record", help="record an agent-supplied transcript")
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "fn", None):
        _build_parser().print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
