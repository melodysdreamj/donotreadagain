"""dnr command-line interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _configure_utf8_stdio() -> None:
    """Keep CLI output stable on Windows legacy code pages and redirected pipes."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, TypeError, ValueError):
            pass


def _cmd_keygen(args) -> int:
    from . import keyring, signing

    _, pub = keyring.default_keypair()
    print(f"default key ready: key_id={signing.key_id(pub)}  ({keyring.home() / 'keys'})")
    return 0


def _cmd_ingest(args) -> int:
    from . import ingest

    embed_record = bool(getattr(args, "embed", False) and not getattr(args, "no_embed", False))
    if Path(args.file).is_dir():
        stats = ingest.backfill(args.file, embed=embed_record, force=args.force, model=args.model)
        return _emit_backfill(args.file, stats, args.format or "plain")

    rec = ingest.ingest(args.file, transcriber=args.transcriber, embed=embed_record,
                        force=args.force, model=args.model)
    if rec is None:
        print(f"{args.file}: already-readable text — no transcription or record needed (read it directly)")
        return 0
    p = rec["provenance"]
    from . import embed, transcribe
    where = "in-file" if embed.has_carrier(args.file) and embed_record else "db-only (index)"
    print(f"ingested {args.file}  [{where}]")
    print(f"  method={p['method']} transcriber={p['transcriber']}")
    print(f"  {rec['content_hash']}")
    if "sig" in rec:
        print(f"  signed key_id={rec['sig']['key_id']}")
    txt = (rec.get("transcript") or {}).get("text") or ""
    if transcribe.is_low_quality(txt):
        print(f"  [dnr] warning: extracted text is thin/garbled ({len(txt)} chars) — likely a scan or bad "
              f"encoding. Redo via vision: `dnr record {args.file} --transcript-file <t.md> --method vision "
              f"--transcriber <your-model>`", file=sys.stderr)
    return 0


def _emit_backfill(folder, stats: dict, fmt: str = "plain") -> int:
    if fmt == "json":
        import json

        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0 if not stats.get("errors") else 1

    print(f"backfilled {folder}: {len(stats['ingested'])} ingested, {len(stats['already'])} already cached, "
          f"{len(stats['agent_needed'])} need agent/vision, {len(stats['low_quality'])} need repair, "
          f"{len(stats['errors'])} errors")
    idx = stats.get("index") or {}
    if idx:
        print(f"indexed {folder}: +{idx.get('indexed', 0)} new, {idx.get('skipped', 0)} skipped, "
              f"{idx.get('removed', 0)} removed, {idx.get('untrusted', 0)} untrusted, "
              f"{idx.get('errored', 0)} errored")
    if stats["agent_needed"]:
        print("\nagent/vision needed:")
        for item in stats["agent_needed"]:
            print(f"  {item['path']} — {item['reason']}")
    if stats["low_quality"]:
        print("\nquality repair needed:")
        for item in stats["low_quality"]:
            print(f"  {item['path']} — {item['reason']}")
    if stats["errors"]:
        print("\nerrors:", file=sys.stderr)
        for item in stats["errors"]:
            print(f"  {item['path']} — {item['error']}", file=sys.stderr)
    return 0 if not stats["errors"] else 1


def _cmd_backfill(args) -> int:
    from . import ingest

    embed_record = bool(getattr(args, "embed", False) and not getattr(args, "no_embed", False))
    stats = ingest.backfill(args.folder, embed=embed_record, force=args.force, model=args.model)
    return _emit_backfill(args.folder, stats, args.format or "plain")


def _cmd_record(args) -> int:
    from . import ingest

    text = Path(args.transcript_file).read_text(encoding="utf-8") if args.transcript_file else args.transcript
    if text is None:
        print("dnr record: provide --transcript or --transcript-file", file=sys.stderr)
        return 2
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    embed_record = bool(getattr(args, "embed", False) and not getattr(args, "no_embed", False))
    rec = ingest.record_supplied(args.file, text, args.method, args.transcriber,
                                 lang=args.lang, tags=tags, embed=embed_record)
    from . import embed
    where = "in-file" if embed.has_carrier(args.file) and embed_record else "db-only (index)"
    print(f"recorded {args.file}: method={args.method} [{where}] {rec['content_hash']}")
    return 0


def _cmd_read(args) -> int:
    from . import ingest

    text = ingest.read_cached(args.file)
    if text is None:
        print(f"[dnr] no valid cached record for {args.file} — read it normally", file=sys.stderr)
        return 0
    from . import transcribe
    if transcribe.is_low_quality(text):
        print(f"[dnr] note: this transcript looks low-quality (empty/mojibake) — consider redoing it "
              f"via vision: `dnr record {args.file} ...`", file=sys.stderr)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_verify(args) -> int:
    from pathlib import Path

    from . import embed, hashing, index, keyring, signing

    rec = index.db_only_record(Path(args.file).parent, args.file)
    where = "db-only"
    if rec is None:
        rec = embed.extract(args.file)
        where = "in-file"
    if rec is None:
        print("no dnr record")
        return 1
    trusted = signing.verify(rec, keyring.default_trust())
    try:
        match = rec.get("content_hash") == hashing.content_hash(args.file)
    except ValueError:
        match = None
    print(f"record: yes ({where}) · signed&trusted: {trusted} · content_hash match: {match}")
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
    import os

    from . import index

    if os.path.isfile(args.folder):
        print(f"[dnr] '{args.folder}' is a file — `dnr query` takes a folder; for one file use `dnr read`.",
              file=sys.stderr)
        return 2

    if args.use:  # reuse a saved query expression (live re-run)
        expr = index.get_query(args.folder, args.use)
        if expr is None:
            print(f"[dnr] no saved query '{args.use}'", file=sys.stderr)
            return 1
    else:
        tags = [t.strip() for t in args.tag.split(",") if t.strip()] if args.tag else []
        any_tags = [t.strip() for t in args.any_tag.split(",") if t.strip()] if args.any_tag else []
        anys = [t.strip() for t in args.any.split(",") if t.strip()] if args.any else []
        expr = {"match": args.match, "any": anys, "tags": tags, "any_tags": any_tags,
                "since": args.since, "until": args.until,
                "where": args.where, "sort": args.sort, "desc": args.desc,
                "dedup": args.dedup, "min_chars": args.min_chars}

    fmt = args.format or "plain"
    sort_col = "start_date" if expr.get("sort") in ("date", "start_date") else expr.get("sort")

    def _emit(rows):
        if fmt == "json":
            import json as _j
            cols = ("path", "start_date", "method", "title", "tags", "content_hash")
            print(_j.dumps([{k: r.get(k) for k in cols} for r in rows], ensure_ascii=False, indent=2))
            return
        for r in rows:
            if fmt == "paths":
                print(r["path"])
                continue
            prefix = f"{(r.get(sort_col) if r.get(sort_col) is not None else '—'):<12}\t" if sort_col else ""
            print((prefix + r["path"] + (f"\t{r['title']}" if r.get("title") else "")).rstrip())

    def _emit_context(rows, term: str):
        from . import index as _index

        if fmt == "json":
            import json as _j

            print(_j.dumps([
                {"path": r["path"], "snippets": _index._snippets((r.get("transcript") or ""), term, args.context)}
                for r in rows
            ], ensure_ascii=False, indent=2))
            return
        for r in rows:
            print(r["path"])
            for s in _index._snippets((r.get("transcript") or ""), term, args.context):
                print(f"    … {s}")

    composed = (expr.get("any") or expr.get("tags") or expr.get("any_tags") or expr.get("since") or expr.get("until")
                or expr.get("where") or expr.get("dedup") or expr.get("min_chars"))
    has_filter = expr.get("match") or composed

    if not has_filter and (args.list or args.use):  # inventory
        rows = index.list_all(args.folder, sort=expr.get("sort") or "path", desc=expr.get("desc"))
        _emit(rows)
    elif has_filter:  # composed: match ∩ tag ∩ time ∩ where
        rows = index.query_compose(
            args.folder, match=expr.get("match"), any_terms=expr.get("any"), tags=expr.get("tags"),
            any_tags=expr.get("any_tags"),
            since=expr.get("since"), until=expr.get("until"), where=expr.get("where"),
            sort=expr.get("sort"), desc=expr.get("desc"), dedup=expr.get("dedup"),
            min_chars=expr.get("min_chars"))
        if expr.get("match") and args.context is not None:
            _emit_context(rows, expr["match"])
        else:
            _emit(rows)
    else:
        print("dnr query: --match/--tag/--since/--until/--where [--context N] [--dedup] [--format json],"
              " --list, or --use LABEL", file=sys.stderr)
        return 2

    hits = len(rows)
    if not hits:
        print("[dnr] no rows match", file=sys.stderr)
    # honesty about optional dates
    if sort_col == "start_date" and hits and all(r.get("start_date") is None for r in rows):
        print("[dnr] note: none of these have a start_date — `--sort date` had no effect "
              "(dates are optional; add one with `dnr date <file> <YYYY-MM-DD>`)", file=sys.stderr)
    if (expr.get("since") or expr.get("until")) and not hits:
        print("[dnr] note: --since/--until only match files that have a start_date (optional, none auto-set)",
              file=sys.stderr)
    if args.save:
        index.save_query(args.folder, args.save, expr)
        warn = " — warning: 0 hits (empty view)" if hits == 0 else ""
        print(f"[dnr] saved query '{args.save}'{warn}", file=sys.stderr)
    if args.use:
        index.log_query_run(args.folder, args.use, hits)
    return 0


def _cmd_date(args) -> int:
    from . import ingest

    if args.date is None and not args.clear:
        cur = ingest.current_date(args.file)
        print(cur if cur else "(no date)")
        return 0
    d = ingest.set_date(args.file, None if args.clear else args.date)
    print(f"start_date: {d or '(cleared)'}")
    return 0


def _cmd_tag(args) -> int:
    from . import ingest

    add = list(args.tags or [])
    remove = [t.strip() for t in args.rm.split(",") if t.strip()] if args.rm else []
    if not add and not remove:
        cur = ingest.current_tags(args.file)
        print(" ".join(cur) if cur else "(no tags)")
        return 0
    tags = ingest.set_tags(args.file, add=add, remove=remove)
    print(f"tags: {' '.join(tags) if tags else '(none)'}")
    return 0


def _cmd_queries(args) -> int:
    import json

    from . import index

    rows = index.list_queries(args.folder)
    if not rows:
        print("[dnr] no saved queries", file=sys.stderr)
        return 0
    for r in rows:
        e = json.loads(r["expr"])
        parts = []
        for k in ("match", "since", "until", "where", "sort"):
            if e.get(k):
                parts.append(f"{k}:{e[k]}")
        if e.get("tags"):
            parts.append("tags:" + ",".join(e["tags"]))
        if e.get("any_tags"):
            parts.append("any-tags:" + ",".join(e["any_tags"]))
        print(f"{r['label']}\t{' '.join(parts)}\t(runs:{r['run_count']}, last_hits:{r['last_hits']})")
    return 0


def _cmd_status(args) -> int:
    from . import index

    c = index.coverage(args.folder)
    if (args.format or "plain") == "json":
        import json

        print(json.dumps(c, ensure_ascii=False, indent=2))
        return 0
    if c["total"] == 0:
        print(f"{args.folder}: no supported files found")
        return 0
    print(f"{args.folder}: {c['usable']}/{c['total']} files have a usable cached transcript "
          f"({c['recorded']} cached, {c['pending']} pending, {c['needs_repair']} need repair)")
    labels = {"model": "images/audio/video (need a model each view)",
              "parse": "PDF/Office (expensive to re-parse)",
              "cheap": "text (no transcription needed)"}
    for kind in ("model", "parse", "cheap"):
        total, rec = c["by_kind"][kind]
        if total:
            usable = c["by_kind_usable"][kind][1]
            repair = sum(1 for p in c["repair_list"] if p["kind"] == kind)
            detail = f"{usable}/{total} usable"
            if repair:
                detail += f" ({repair} repair)"
            elif rec != usable:
                detail += f" ({rec} cached)"
            print(f"  {labels[kind]:42} {detail}")
    if args.pending:
        pend = [p for p in c["pending_list"] if p["kind"] != "cheap"]
        repair = [p for p in c["repair_list"] if p["kind"] != "cheap"]
        if not pend and not repair:
            print("\nnothing pending.")
        if pend:
            print(f"\npending transcription ({len(pend)}):")
            for p in pend:
                print(f"  [{p['kind']}] {p['path']}")
        if repair:
            print(f"\nlow-quality — repair/re-OCR ({len(repair)}):")
            for p in repair:
                print(f"  [{p['kind']}] {p['path']}")
        return 0
    if c["should_offer_transcribe"]:
        print()
        print(f"expensive cache gaps: {c['pending_model']} model-only pending + "
              f"{c['pending_parse']} parse-heavy pending + {c['repair_model'] + c['repair_parse']} repairs "
              f"(`dnr status <folder> --pending` to list).")
        print("Do not pre-transcribe just because they are pending. When the current task needs one, "
              "read/transcribe it once and cache it, then:")
        print("  dnr ingest <born-digital> · dnr record <image/audio/video> · dnr index <folder>")
    return 0


def _cmd_strip(args) -> int:
    from pathlib import Path

    from . import embed, index

    removed = embed.strip(args.file)  # in-file carrier (+ any legacy sidecar cleanup)
    removed = index.remove_record(Path(args.file).parent, args.file) or removed  # db-only record
    if removed:
        print(f"stripped dnr record from {args.file}")
        return 0
    print(f"no dnr record in {args.file}", file=sys.stderr)
    return 1


def _cmd_validate(args) -> int:
    from pathlib import Path

    from . import embed, index, schema

    rec = index.db_only_record(Path(args.file).parent, args.file)
    if rec is None:
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
    from . import bootstrap, keyring, signing

    _, pub = keyring.default_keypair()  # ensure a signing key exists
    print(f"dnr ready · signing key_id={signing.key_id(pub)}")
    if args.agent_file:
        for path in args.agent_file:
            status = bootstrap.install_agent_file(path)
            print(f"{status} agent bootstrap in {path}")
    if not args.agent_file:
        print("no per-folder note is installed — each file self-describes via its `_about` pointer.")
    print("tell your agent: Use dnr for this folder.")
    print("agent contract: dnr read before parsing; dnr index/query before opening folder hits;")
    print("cache expensive misses with dnr ingest/record.")
    print(f"agents fetch the skill once from {bootstrap.SKILL_RAW_URL} (or run `dnr skill`).")
    return 0


def _cmd_skill(args) -> int:
    from . import skill

    sys.stdout.write(skill.skill_md())
    if not skill.skill_md().endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dnr", description="Read once, never again.")
    p.add_argument("-V", "--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("keygen", help="create/show the local signing key").set_defaults(fn=_cmd_keygen)

    pi = sub.add_parser("ingest", help="transcribe (local, auto by type) + record + sign into .dnr.db")
    pi.add_argument("file")
    pi.add_argument("--transcriber", default=None, help="override the local provider (text-extract, whisper)")
    pi.add_argument("--model", default=None,
                    help="Whisper model for audio ingest/backfill (default: small; e.g. base|small|medium)")
    pi.add_argument("--embed", action="store_true",
                    help="opt in to writing the record into the file's metadata when supported")
    pi.add_argument("--no-embed", action="store_true", help=argparse.SUPPRESS)
    pi.add_argument("--force", action="store_true", help="re-ingest even if a valid record exists")
    pi.add_argument("--format", choices=["plain", "json"], help="folder ingest output format")
    pi.set_defaults(fn=_cmd_ingest)

    pb = sub.add_parser("backfill", help="ingest locally-processable files in a folder; list agent-needed gaps")
    pb.add_argument("folder")
    pb.add_argument("--model", default=None,
                    help="Whisper model for audio files (default: small; e.g. base|small|medium)")
    pb.add_argument("--embed", action="store_true",
                    help="opt in to writing records into file metadata when supported")
    pb.add_argument("--no-embed", action="store_true", help=argparse.SUPPRESS)
    pb.add_argument("--force", action="store_true", help="re-ingest even if valid records exist")
    pb.add_argument("--format", choices=["plain", "json"], help="output format")
    pb.set_defaults(fn=_cmd_backfill)

    pr = sub.add_parser("record", help="record an agent-supplied transcript (follows the verbatim guide)")
    pr.add_argument("file")
    pr.add_argument("--transcript")
    pr.add_argument("--transcript-file")
    pr.add_argument("--method", default="vision")
    pr.add_argument("--transcriber", default="agent")
    pr.add_argument("--lang")
    pr.add_argument("--tags", help="comma-separated tags")
    pr.add_argument("--embed", action="store_true",
                    help="opt in to writing the record into the file's metadata when supported")
    pr.add_argument("--no-embed", action="store_true", help=argparse.SUPPRESS)
    pr.set_defaults(fn=_cmd_record)

    prd = sub.add_parser("read", help="print the cached transcript if trusted, else fall back")
    prd.add_argument("file")
    prd.set_defaults(fn=_cmd_read)

    pv = sub.add_parser("verify", help="check a file's dnr record")
    pv.add_argument("file")
    pv.set_defaults(fn=_cmd_verify)

    sub.add_parser("guide", help="print the verbatim transcription guide (for the agent)").set_defaults(fn=_cmd_guide)
    sub.add_parser("types", help="list supported file types + transcription methods").set_defaults(fn=_cmd_types)

    pst = sub.add_parser("status", help="folder transcript coverage + pending cache gaps")
    pst.add_argument("folder")
    pst.add_argument("--pending", action="store_true", help="list the files still needing transcription")
    pst.add_argument("--format", choices=["plain", "json"], help="output format")
    pst.set_defaults(fn=_cmd_status)

    pd = sub.add_parser("date", help="show/set/clear a file's start_date (optional; dnr never infers it)")
    pd.add_argument("file")
    pd.add_argument("date", nargs="?", help="YYYY-MM-DD (omit to show current)")
    pd.add_argument("--clear", action="store_true", help="remove the start_date")
    pd.set_defaults(fn=_cmd_date)

    pix = sub.add_parser("index", help="harvest a folder's records into .dnr.db")
    pix.add_argument("folder")
    pix.set_defaults(fn=_cmd_index)

    pq = sub.add_parser("query", help="query a folder's index")
    pq.add_argument("folder")
    pq.add_argument("--match", help="full-text search (FTS5 trigram; <3-char terms via substring)")
    pq.add_argument("--any", help="match ANY of these terms (comma-separated OR; e.g. 가압류,보전,집행)")
    pq.add_argument("--context", nargs="?", const=200, type=int, metavar="N",
                    help="with --match: show ±N chars around each hit (default 200)")
    pq.add_argument("--tag", help="tag(s) the file must have; comma-separated = AND (e.g. 가압류,2025)")
    pq.add_argument("--any-tag", dest="any_tag",
                    help="tag(s) where any may match; comma-separated = OR (e.g. 우리측,상대측)")
    pq.add_argument("--since", help="start_date >= (e.g. 2025-01-01)")
    pq.add_argument("--until", help="start_date <= (e.g. 2026-06-30)")
    pq.add_argument("--where", help="SQL WHERE over the fixed columns")
    pq.add_argument("--list", action="store_true", help="list every indexed record")
    pq.add_argument("--sort", help="sort by: path|mtime|indexed_at|bytes|title|date")
    pq.add_argument("--desc", action="store_true", help="descending sort")
    pq.add_argument("--dedup", action="store_true", help="collapse identical-content files (content_hash)")
    pq.add_argument("--min-chars", type=int, metavar="N", dest="min_chars",
                    help="drop near-empty transcripts (< N chars)")
    pq.add_argument("--format", choices=["plain", "paths", "json"], help="output format (default plain)")
    pq.add_argument("--save", metavar="LABEL", help="save this composed query for reuse")
    pq.add_argument("--use", metavar="LABEL", help="re-run a saved query (live)")
    pq.set_defaults(fn=_cmd_query)

    pqs = sub.add_parser("queries", help="list saved queries for a folder")
    pqs.add_argument("folder")
    pqs.set_defaults(fn=_cmd_queries)

    ptg = sub.add_parser("tag", help="show/add/remove a file's tags (e.g. dnr tag f.pdf 가압류 면탈)")
    ptg.add_argument("file")
    ptg.add_argument("tags", nargs="*", help="tags to add (no args = show current)")
    ptg.add_argument("--rm", help="comma-separated tags to remove")
    ptg.set_defaults(fn=_cmd_tag)

    pin = sub.add_parser("init", help="ensure a signing key + optionally add a local agent-file bootstrap")
    pin.add_argument("--agent-file", action="append", metavar="PATH",
                     help="append or upgrade the dnr bootstrap in AGENTS.md, CLAUDE.md, etc.; repeatable")
    pin.set_defaults(fn=_cmd_init)
    sub.add_parser("skill", help="print the dnr agent skill (SKILL.md) for an agent to fetch/install").set_defaults(fn=_cmd_skill)

    ps = sub.add_parser("strip", help="remove the dnr record before sharing")
    ps.add_argument("file")
    ps.set_defaults(fn=_cmd_strip)

    pval = sub.add_parser("validate", help="validate a file's record against the dnr-0.1 schema")
    pval.add_argument("file")
    pval.set_defaults(fn=_cmd_validate)

    sub.add_parser("schema", help="print the dnr record JSON Schema").set_defaults(fn=_cmd_schema)
    return p


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
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
