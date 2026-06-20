"""dnr command-line entry point (M7 — skeleton).

Full subcommands (init/ingest/index/query/read/verify/strip) are built out in M7.
This skeleton exposes the wiring and reports what's implemented so far.
"""
from __future__ import annotations

import sys

from . import __version__

_COMMANDS = ("init", "ingest", "index", "query", "read", "verify", "seal", "strip")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("dnr — read once, never again")
        print(f"  version {__version__}")
        print("  commands: " + " | ".join(_COMMANDS) + "  (in progress — see MILESTONES.md)")
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(__version__)
        return 0
    if argv[0] in _COMMANDS:
        print(f"dnr {argv[0]}: not implemented yet (tracked in MILESTONES.md)", file=sys.stderr)
        return 2
    print(f"dnr: unknown command '{argv[0]}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
