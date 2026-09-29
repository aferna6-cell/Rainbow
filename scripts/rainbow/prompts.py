"""Prompts + JSON schemas for each headless coach step.

The coach persona and protocol come from CLAUDE.md, which headless Claude
Code loads automatically from the repo root. These prompts only add the
scripted-mode contract: the script owns the journal, bans and counters;
Claude returns structured judgement.
"""

SCRIPTED_MODE = (
    "SCRIPTED MODE: scripts/coach.py owns data/sessions/ and the Live counters "
    "section of knowledge/opponent/gio.md. Do not create or edit files unless this "
    "prompt says so. Bans listed as confirmed are the ONLY logged bans; your "
    "recommendations are never logged bans."
)

CALL_SCHEMA = {
    "type": "object",
    "properties": {"call": {"type": "string", "description": "The full pre-round call block."}},
    "required": ["call"],
}

ROUND_SCHEMA = {
    "type": "object",
    "properties": {
        "side": {"type": "string", "enum": ["ATK", "DEF"]},
        "my_op": {"type": "string"},
        "his_op": {"type": "string"},
        "result": {"type": "string", "enum": ["W", "L"]},
        "what_happened": {"type": "string"},
        "counters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tendency": {"type": "string"}, "hit": {"type": "boolean"}},
                "required": ["tendency", "hit"],
            },
        },
        "next_call": {"type": "string"},
    },
    "required": ["side", "my_op", "his_op", "result", "what_happened", "counters", "next_call"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
    },
    "required": ["summary"],
}

INGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "ingested": {"type": "array", "items": {"type": "string"}},
        "skipped": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"file": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["file", "reason"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["ingested", "skipped", "summary"],
}


def _bans(mine: list[str], his: list[str]) -> str:
    return f"mine [{', '.join(mine) or 'none'}] · his [{', '.join(his) or 'none'}]"


def start(session_file: str, header: str, recent: list[str], setup: str,
          round_no: int, mine: list[str], his: list[str], counters: list[str]) -> str:
    recent_txt = ", ".join(recent) or "none yet (first session: say so, lean on principles.md)"
    return f"""{SCRIPTED_MODE}

Session start (CLAUDE.md §1). Read every file under knowledge/ now, plus these
past session files: {recent_txt}. Today's journal is {session_file}
("{header}"); read it too if it has rows — we may be resuming.
Setup from the player: {setup}
Confirmed cumulative bans so far (current ruleset): {_bans(mine, his)}.
Live counters: {'; '.join(counters) or 'none yet'}.

Return in `call` the Round {round_no} pre-round call, exactly in the CLAUDE.md §2
format. Nothing else."""


def round_report(round_no: int, report: str, my_ban: str, his_ban: str,
                 mine: list[str], his: list[str], counters: list[str]) -> str:
    return f"""{SCRIPTED_MODE}

Round {round_no} result from the player: "{report}"
Confirmed bans THIS round (script-logged): me={my_ban or 'none confirmed'}, him={his_ban or 'none confirmed'}.
Cumulative confirmed bans incl. this round: {_bans(mine, his)}.
Current live counters: {'; '.join(counters) or 'none yet'}.

Fill the fields:
- side: the side I played this round.
- my_op: the operator I say I played; only if I didn't say, the one you called.
- his_op: his operator if known from my report or the round, else "?".
- result: W or L.
- what_happened: one line, name the rooms.
- counters: each opponent tendency this round tested, hit=true if he did it.
  Reuse an existing counter name VERBATIM when it applies. Add a new tendency
  only for a distinct habit visible in my report. Never invent observations.
- next_call: the Round {round_no + 1} pre-round call in the CLAUDE.md §2 format,
  obeying the unpredictability rule and the ban state above."""


def question(text: str) -> str:
    return f"{SCRIPTED_MODE}\n\nBetween-rounds question (answer caveman-terse, no new call unless asked): {text}"


def summary(wins: int, losses: int, note: str) -> str:
    return f"""{SCRIPTED_MODE}

Session over (CLAUDE.md §4). Journal score: {wins}-{losses} (me-him).
Player note: "{note or 'none'}" — a score stated there overrides the journal.
You MAY edit knowledge/opponent/gio.md, but ONLY to append to "Burned exploits"
or "Proven positives" what this session proved. Never touch "Live counters".
Return `summary`: exactly 5 lines — score; what worked; what he adapted to;
top 2 tendencies learned; opening plan for next session."""


def refresh_meta(today: str) -> str:
    return f"""Meta refresh (CLAUDE.md §1). knowledge/meta/current-meta.md is stale.
WebSearch the CURRENT Rainbow Six Siege season, latest patch notes, new or
reworked operators, and ban-rate data. Priority: Ubisoft official > current
YouTube/community. Rewrite knowledge/meta/current-meta.md keeping its section
structure, set the line to exactly `Last verified: **{today}** (web-checked).`,
keep the 1v1 translation notes, mark anything you could not verify as
unverified, and list sources. Edit no other file. Reply with a 3-line summary."""


def ingest(files: list[str]) -> str:
    return f"""Ingest (CLAUDE.md "Ingesting the gameplay snapshot"). New raw files:
{chr(10).join('- ' + f for f in files)}
Read each fully. Extract only opponent-behavior and player-self claims into
knowledge/opponent/gio.md, each with a source line (raw/<file>#<section>) and a
starting evidence count. Never modify or delete raw files; never invent
tendencies. Do not edit the "Live counters" section. If a file cannot be read
(binary format you can't parse), put it in `skipped` with the reason.
Return `ingested` (file names done), `skipped`, and a one-paragraph `summary`."""
