"""Rainbow automation: scripted session loop around the CLAUDE.md coach protocol.

Deterministic bookkeeping (journal rows, confirmed bans, evidence counters,
meta staleness, raw-file ingest tracking, commits) lives in plain Python.
Judgement (round calls, parsing "what happened", summaries, meta research,
ingest extraction) is delegated to headless `claude -p`.
"""
