#!/usr/bin/env python3
"""Stand-in for `claude -p --output-format json` used by the tests.

Picks a canned structured reply from the --json-schema keys, appends every
invocation to $FAKE_CLAUDE_LOG, and for the meta-refresh prompt stamps the
meta file the way the real coach would.
"""

import json
import os
import re
import sys
from pathlib import Path

args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
schema = json.loads(args[args.index("--json-schema") + 1]) if "--json-schema" in args else None
resume = args[args.index("--resume") + 1] if "--resume" in args else None

with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"prompt": prompt, "resume": resume, "args": args}) + "\n")

if os.environ.get("FAKE_CLAUDE_FAIL"):
    print(json.dumps({"is_error": True, "result": "boom"}))
    sys.exit(1)

text, data = "ok", None
keys = set((schema or {}).get("properties", {}))
if keys == {"call"}:
    data = {"call": "── ROUND 1 · Defend ──\nPICK: Mozzie"}
elif "next_call" in keys:
    n = int(re.search(r"Round (\d+) result", prompt).group(1))
    data = {
        "side": "DEF", "my_op": "Mozzie", "his_op": "Fuze", "result": "W",
        "what_happened": "he came Laundry Stairs | pests caught drone",
        "counters": [{"tendency": "Attacks Basement via Laundry", "hit": True},
                     {"tendency": "bans what beat him last", "hit": False}],
        "next_call": f"── ROUND {n + 1} · Attack ──",
    }
elif keys == {"summary"}:
    data = {"summary": ["1-0", "Mozzie offset", "none yet", "Laundry route", "open Smoke"]}
elif "ingested" in keys:
    files = re.findall(r"^- (.+)$", prompt, re.M)
    data = {"ingested": [f for f in files if not f.endswith(".bin")],
            "skipped": [{"file": f, "reason": "binary"} for f in files if f.endswith(".bin")],
            "summary": "added claims"}
elif "Meta refresh" in prompt:
    today = re.search(r"Last verified: \*\*(\d{4}-\d{2}-\d{2})\*\*", prompt).group(1)
    meta = Path(os.environ["RAINBOW_ROOT"]) / "knowledge/meta/current-meta.md"
    if not os.environ.get("FAKE_CLAUDE_SKIP_META_WRITE"):
        meta.write_text(f"# Current Meta Snapshot\n\nLast verified: **{today}** (web-checked).\n")
    text = "refreshed"
else:
    text = "answer: hold Supply offset"

print(json.dumps({"type": "result", "is_error": False, "session_id": "sess-1", "result":
                  json.dumps(data) if data is not None else text,
                  "structured_output": data, "total_cost_usd": 0.01}))
