"""CLI: python3 scripts/coach.py <play|auto|refresh-meta|ingest|status>."""

import argparse
import datetime as dt
import sys

from . import claude, counters, ingest, journal, maintenance, meta, paths, play


def _status(today: dt.date) -> int:
    age = meta.age_days(paths.meta_file(), today)
    print(f"meta: {'unknown age' if age is None else f'{age}d old'}"
          f"{' — STALE' if meta.is_stale(paths.meta_file(), today) else ''}")
    pending = ingest.pending()
    print(f"raw/ pending ingest: {', '.join(p.name for p in pending) or 'none'}")
    session = journal.session_path(today)
    if session.exists():
        w, l = journal.score(session)
        mine, his = journal.cumulative_bans(session)
        print(f"today {session.name}: {w}-{l} · bans mine {mine} his {his}")
    else:
        print("today: no session yet")
    for c in counters.load(paths.gio_file()):
        print("  " + c.to_line()[2:])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coach.py", description=__doc__)
    parser.add_argument("--date", help="override today (YYYY-MM-DD)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("play", help="run a live coaching session")
    p.add_argument("--map", default="Oregon")
    p.add_argument("--rules", default="1v1 bomb, cumulative bans")
    p.add_argument("--opponent", default="Gio")
    p.add_argument("--first-side", choices=["atk", "def"])
    p.add_argument("--new", action="store_true", help="start a second session today (-2 file)")
    p.add_argument("--skip-maintenance", action="store_true", help="skip meta refresh + ingest preflight")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--push", action="store_true")

    a = sub.add_parser("auto", help="unattended upkeep: meta refresh if stale + ingest new raw files + commit")
    a.add_argument("--push", action="store_true")

    r = sub.add_parser("refresh-meta", help="web-refresh knowledge/meta/current-meta.md")
    r.add_argument("--force", action="store_true")

    sub.add_parser("ingest", help="ingest new files in knowledge/opponent/raw/")
    sub.add_parser("status", help="meta age, pending raw files, today's score, counters")

    args = parser.parse_args(argv)
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    try:
        if args.cmd == "play":
            return play.run(args, sys.stdout, input)
        if args.cmd == "auto":
            code, log = maintenance.auto(today, args.push)
            print("\n".join(log))
            return code
        if args.cmd == "refresh-meta":
            print(maintenance.refresh_meta(today, force=args.force))
        elif args.cmd == "ingest":
            print(maintenance.run_ingest())
        elif args.cmd == "status":
            return _status(today)
    except claude.ClaudeError as exc:
        print(f"!! {exc}", file=sys.stderr)
        return 1
    return 0
