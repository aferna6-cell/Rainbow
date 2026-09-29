# Rainbow — R6 Siege 1v1 Strategy Coach

A terminal coach for Rainbow Six Siege 1v1s (vs. Gio), built as a
Claude Code repo. No overlay is possible — Siege on Xbox exposes no log file
or live match API (unlike Hearthstone's `Power.log` that powers
[Replay](https://github.com/aferna6-cell/Replay)) — so this is a
**between-rounds coach with a persistent memory**, not a telemetry tool.

## What it does

Every round, before you pick:

```
── ROUND 4 · Chalet · Defend ──
BAN:    Jackal — he roam-hunted you with it twice last session
HIS BAN (likely): Frost → fallback pick: Kapkan
PICK:   Vigil — K1A holo, C4, bulletproof cam

GAMEPLAN
  Setup:  hold Wine Cellar off-site from Snowmobile Garage stairs; C4 in hand;
          bulletproof cam deep Blue Hallway; leave Bar hatch unreinforced (soundboard)
  Early:  kill his first drone at Main Entrance choke, then go silent
  Mid:    he clears Bar-side first 70% of the time — pre-hold the Garage door angle
  Clock:  at 1:00 rotate through Cellar back to obj; he panics-pushes late
  IF he drones Garage stairs first THEN rotate obj immediately and anchor
PATTERN: breaks your 3-round streak of anchoring the objective room
```

Then you play the round on the Xbox, type one line back (`w` / `l — he did X`),
and it adapts: journal updated, opponent model counters updated, next call
adjusted. Over sessions it builds a real model of how Gio plays —
that model, not a tier list, is the edge.

## Quick start

```bash
cd Rainbow
claude          # the coach persona + protocol load from CLAUDE.md
# then: "new session, Oregon, bomb vs Gio, I defend first"
```

Feed it your existing gameplay-pattern notes: drop them in
`knowledge/opponent/raw/` and say **"ingest"**.

## Layout

| Path | Role |
|---|---|
| `CLAUDE.md` | The coach: persona, round protocol, adaptation + ingest rules |
| `knowledge/dueling/principles.md` | 1v1 theory — how 1v1 re-prices the 5v5 meta |
| `knowledge/meta/current-meta.md` | Season/patch/ban-rate snapshot, self-refreshing via web search when stale |
| `knowledge/operators/` | Attacker/defender pricing **for 1v1 specifically** |
| `knowledge/maps/oregon-vs-gio.md` | **The Oregon counterbook** — route-first plans per site vs Gio |
| `knowledge/maps/notes.md` | Per-map 1v1 notes, grown from play |
| `knowledge/research/` | Current YouTube guide transcripts (source-of-truth geometry) |
| `knowledge/opponent/gio.md` | The opponent model — evidence-counted tendencies |
| `knowledge/opponent/raw/` | Drop zone for gameplay-pattern snapshots ("ingest") |
| `data/sessions/` | Round-by-round journal, one file per session |
| `scripts/coach.py` | Automation: session loop, upkeep job (see below) |

## Why this beats a custom GPT / Claude project

- **It writes back.** A GPT/project reads static knowledge; this coach
  updates the opponent model and journal after every round, so it's sharper
  next week without you re-uploading anything.
- **Live meta.** It web-checks the current season/patch/ban data when its
  snapshot goes stale, instead of answering from training data.
- **1v1-native strategy.** The knowledge base explicitly re-prices operators
  and strategy for 1v1 (traps/intel-denial up, hard breach down, psychology
  as a first-class pillar) — the thing generic tools get wrong.
- **Versioned.** Every session, model update, and meta refresh is a git
  commit you can inspect or revert.

## Automation

`scripts/coach.py` runs the whole protocol as a loop around headless Claude
Code (`claude -p`). The script does the bookkeeping deterministically —
journal rows, confirmed-only cumulative bans, evidence counters (≥60% over
≥5 → confirmed, 2 straight misses → broken), meta staleness, ingest tracking,
the end-of-session commit. Claude does the judgement: the round call, reading
your one-line report, the 5-line summary, meta research, ingest extraction.

```bash
python3 scripts/coach.py play --first-side def         # Oregon · bomb · Gio by default
python3 scripts/coach.py play --map Chalet --rules "bomb, bans reset each round"
python3 scripts/coach.py status                        # meta age, pending raw files, score, counters
python3 scripts/coach.py refresh-meta [--force]        # web-refresh knowledge/meta/current-meta.md
python3 scripts/coach.py ingest                        # new files in knowledge/opponent/raw/
scripts/auto.sh [--push]                               # unattended: refresh-if-stale + ingest + commit
```

In `play`: it refreshes a stale meta snapshot and ingests new raw files, reads
`knowledge/` once, prints the Round 1 call, then waits between rounds for:

| Type | Does |
|---|---|
| `ban Fuze` / `hisban Mute` | confirm this round's bans (the only bans ever logged) |
| `w` / `l — he played Fuze, drilled me in Laundry` | log the round, update counters, print the next call |
| `reset bans` | new ruleset / no OT bans |
| `done 7-5` | 5-line summary, model update, commit (no push unless `--push`) |
| `quit` | stop; `play` again resumes the same session and conversation |
| anything else | a question to the coach, not logged |

Unattended upkeep: run `scripts/auto.sh` daily from cron
(`17 9 * * * /path/to/Rainbow/scripts/auto.sh --push`) or from a Claude Code
Routine. It only calls Claude when the meta is >21 days old or `raw/` has a
file not listed in `raw/.ingested`.

Needs Python 3.10+ and the Claude Code CLI signed in. `RAINBOW_MODEL=sonnet`
picks the model (default: your Claude Code default). Tests run offline
against a fake CLI: `python3 -m unittest discover -s tests`.

## Later (optional)

- Pull Gio's platform stats from a tracker site into `raw/` for
  tendencies (op pick rates) between sessions.
- If you ever play on PC, a Replay-style capture layer could be revisited;
  on Xbox there is nothing to parse.
