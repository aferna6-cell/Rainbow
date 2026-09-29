"""The live session loop: start → (call → play → report) × N → summary → commit."""

import datetime as dt
import json
import re
from pathlib import Path

from . import claude, counters, gitops, journal, maintenance, paths, prompts

HELP = """commands between rounds:
  w | l [— what happened]   report the round (e.g. `l — he played Fuze, drilled me in Laundry`)
  ban <op> / hisban <op>    confirm this round's bans (only confirmed bans are logged)
  ban - / hisban -          clear a confirmation
  reset bans                bans reset (new ruleset / no OT bans)
  done [note/score]         end session: summary, model update, commit
  quit                      stop now; `play` again later resumes this session
  anything else             ask the coach a question (not logged)"""

RESULT_RE = re.compile(r"^(?P<wl>[wl])(?:\s*[-—:,]\s*|\s+|$)(?P<rest>.*)$", re.IGNORECASE)


def _state_path(session_file: Path) -> Path:
    return paths.sessions_dir() / ".state" / f"{session_file.stem}.json"


def _load_state(session_file: Path) -> dict:
    path = _state_path(session_file)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_state(session_file: Path, state: dict) -> None:
    path = _state_path(session_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def _counter_lines() -> list[str]:
    return [c.to_line()[2:] for c in counters.load(paths.gio_file())]


def _rel(path: Path) -> str:
    return str(path.relative_to(paths.root()))


class Session:
    def __init__(self, session_file: Path, out, inp):
        self.file = session_file
        self.out = out
        self.inp = inp
        self.state = _load_state(session_file)
        self.my_ban = ""
        self.his_ban = ""
        self.cost = 0.0

    def say(self, text: str = "") -> None:
        print(text, file=self.out, flush=True)

    def ask(self, prompt: str, schema: dict | None = None, tools=claude.READ_ONLY) -> claude.Reply:
        reply = claude.run(prompt, schema=schema, resume=self.state.get("claude_session"), tools=tools)
        if reply.session_id:
            self.state["claude_session"] = reply.session_id
            _save_state(self.file, self.state)
        self.cost += reply.cost_usd
        return reply

    def bans_with_pending(self) -> tuple[list[str], list[str]]:
        mine, his = journal.cumulative_bans(self.file)
        return mine + ([self.my_ban] if self.my_ban else []), his + ([self.his_ban] if self.his_ban else [])

    def open(self, setup: str) -> None:
        mine, his = journal.cumulative_bans(self.file)
        recent = [_rel(p) for p in journal.recent_sessions(exclude=self.file)]
        prompt = prompts.start(_rel(self.file), journal.header(self.file), recent, setup,
                               journal.next_round(self.file), mine, his, _counter_lines())
        self.say("coach reading knowledge/ …")
        # A resumed session keeps its conversation; a fresh one starts a new Claude session.
        self.say(self.ask(prompt, prompts.CALL_SCHEMA).data["call"])

    def report(self, wl: str, rest: str) -> None:
        n = journal.next_round(self.file)
        mine, his = self.bans_with_pending()
        text = f"{wl.upper()}" + (f" — {rest}" if rest else "")
        data = self.ask(prompts.round_report(n, text, self.my_ban, self.his_ban, mine, his, _counter_lines()),
                        prompts.ROUND_SCHEMA).data
        row = journal.Row(n, data["side"], self.my_ban, self.his_ban, data["my_op"], data["his_op"],
                          wl.upper(), data["what_happened"])  # the player's W/L wins over the model's
        journal.append_row(self.file, row)
        touched = counters.apply(paths.gio_file(), data.get("counters", []))
        self.my_ban = self.his_ban = ""
        w, l = journal.score(self.file)
        self.say(f"logged R{n} {row.result} ({w}-{l})" + "".join(f"\n  · {c.to_line()[2:]}" for c in touched))
        self.say()
        self.say(data["next_call"])

    def finish(self, note: str, commit: bool, push: bool) -> None:
        w, l = journal.score(self.file)
        reply = self.ask(prompts.summary(w, l, note), prompts.SUMMARY_SCHEMA, tools=("Read", "Edit"))
        journal.write_summary(self.file, reply.data["summary"])
        self.say("\n".join(reply.data["summary"]))
        if commit:
            msg = f"session {self.file.stem}: {w}-{l}, notes + model update"
            self.say(gitops.commit(msg, [_rel(self.file), _rel(paths.gio_file())], push=push))

    def loop(self, commit: bool, push: bool) -> None:
        self.say(HELP)
        while True:
            try:
                line = self.inp().strip()
            except EOFError:
                self.say("\ninput closed — session left open; run `play` again to resume")
                return
            if not line:
                continue
            low = line.lower()
            try:
                if low in ("help", "?"):
                    self.say(HELP)
                elif low == "quit":
                    self.say("session left open; run `play` again to resume")
                    return
                elif low.startswith("done") or low == "end":
                    self.finish(line[4:].strip(" —-:"), commit, push)
                    return
                elif low.startswith("hisban "):
                    self.his_ban = "" if line[7:].strip() == "-" else line[7:].strip()
                    self.say(f"his ban this round: {self.his_ban or 'cleared'} · cumulative {self.bans_with_pending()}")
                elif low.startswith("ban "):
                    self.my_ban = "" if line[4:].strip() == "-" else line[4:].strip()
                    self.say(f"my ban this round: {self.my_ban or 'cleared'} · cumulative {self.bans_with_pending()}")
                elif low in ("reset bans", "bans reset"):
                    journal.mark_bans_reset(self.file)
                    self.my_ban = self.his_ban = ""
                    self.say("bans reset — cumulative state cleared")
                elif m := RESULT_RE.match(line):
                    self.report(m["wl"], m["rest"].strip())
                else:
                    self.say(self.ask(prompts.question(line)).text)
            except claude.ClaudeError as exc:
                self.say(f"!! coach call failed: {exc}\n   nothing was logged for that input — retry it")
            self.say(f"[{self.file.name} · spent ${self.cost:.2f}]")


def run(args, out, inp) -> int:
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    if not args.skip_maintenance:
        for msg in maintenance.preflight(today, out):
            print(msg, file=out)
    session_file = journal.session_path(today, new=args.new)
    fresh = not session_file.exists()
    if fresh:
        journal.create(session_file, today, args.map, args.rules, args.opponent)
    session = Session(session_file, out, inp)
    setup = (f"map {args.map}; rules {args.rules}; opponent {args.opponent}; "
             f"my first side {args.first_side or 'not stated'}")
    if not fresh:
        setup = f"RESUMING {session_file.name} at round {journal.next_round(session_file)}. " + setup
    try:
        session.open(setup)
    except claude.ClaudeError as exc:
        print(f"!! could not start coach: {exc}", file=out)
        return 1
    session.loop(commit=not args.no_commit, push=args.push)
    return 0
