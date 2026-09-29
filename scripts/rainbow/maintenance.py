"""Between-session upkeep: meta refresh when stale, ingest of new raw files.

Used by `play` as a preflight and by `auto` (the unattended cron/Routine job).
"""

import datetime as dt

from . import claude, gitops, ingest, meta, paths, prompts

WEB_TOOLS = ("WebSearch", "WebFetch", "Read", "Edit", "Write")
INGEST_TOOLS = ("Read", "Glob", "Grep", "Edit")


def _rel(path) -> str:
    return str(path.relative_to(paths.root()))


def refresh_meta(today: dt.date, force: bool = False) -> str:
    path = paths.meta_file()
    if not force and not meta.is_stale(path, today):
        return f"meta fresh ({meta.age_days(path, today)}d old)"
    reply = claude.run(prompts.refresh_meta(today.isoformat()), tools=WEB_TOOLS, timeout=1200)
    if meta.last_verified(path) != today:
        raise claude.ClaudeError("meta refresh finished but 'Last verified' was not set to today")
    return "meta refreshed:\n" + reply.text.strip()


def run_ingest() -> str:
    files = ingest.pending()
    if not files:
        return "raw/: nothing new to ingest"
    reply = claude.run(prompts.ingest([f.name for f in files]), schema=prompts.INGEST_SCHEMA,
                       tools=INGEST_TOOLS, timeout=1200)
    done = [f for f in files if f.name in set(reply.data["ingested"])]
    ingest.mark(done)
    lines = [f"ingested {len(done)}/{len(files)}: {reply.data['summary']}"]
    lines += [f"  skipped {s['file']}: {s['reason']}" for s in reply.data["skipped"]]
    return "\n".join(lines)


def _steps(today: dt.date):
    return (("meta", lambda: refresh_meta(today)), ("ingest", run_ingest))


def preflight(today: dt.date, out) -> list[str]:
    if meta.is_stale(paths.meta_file(), today):
        print("meta snapshot is stale — web-refreshing before coaching (takes a few minutes) …", file=out, flush=True)
    messages = []
    for label, step in _steps(today):
        try:
            messages.append(step())
        except claude.ClaudeError as exc:
            messages.append(f"!! {label} step failed, coaching anyway: {exc}")
    return messages


def auto(today: dt.date, push: bool) -> tuple[int, list[str]]:
    """Unattended job: refresh + ingest, then commit what changed. Returns (exit code, log)."""
    log, failed = [], False
    for label, step in _steps(today):
        try:
            log.append(step())
        except claude.ClaudeError as exc:
            failed = True
            log.append(f"!! {label} failed: {exc}")
    targets = [_rel(paths.meta_file()), _rel(paths.gio_file()), _rel(ingest.manifest_path())]
    log.append(gitops.commit(f"auto {today.isoformat()}: meta/ingest upkeep", targets, push=push))
    return (1 if failed else 0), log
