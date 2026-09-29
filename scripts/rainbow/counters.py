"""Evidence counters in the '## Live counters' section of the opponent model.

Line format:  - <tendency> — <hits>/<obs> — <status>[ · miss streak <k>]
Rules (CLAUDE.md §3): confirmed at >=60% over >=5 observations; broken after
two consecutive misses; a hit clears the streak and re-derives the status.
"""

import re
from dataclasses import dataclass
from pathlib import Path

SECTION = "## Live counters"
FORMAT_NOTE = "(managed by scripts/coach.py — `- tendency — hits/obs — status[ · miss streak k]`)"
LINE_RE = re.compile(
    r"^- (?P<name>.+?) — (?P<hits>\d+)/(?P<obs>\d+) — (?P<status>hypothesis|confirmed|broken)"
    r"(?: · miss streak (?P<streak>\d+))?\s*$"
)
CONFIRM_MIN_OBS = 5
CONFIRM_RATE = 0.6
BREAK_STREAK = 2


@dataclass
class Counter:
    name: str
    hits: int = 0
    obs: int = 0
    status: str = "hypothesis"
    streak: int = 0

    def record(self, hit: bool) -> None:
        self.obs += 1
        if hit:
            self.hits += 1
            self.streak = 0
        else:
            self.streak += 1
        if self.streak >= BREAK_STREAK:
            self.status = "broken"
        elif hit or self.status != "broken":
            confirmed = self.obs >= CONFIRM_MIN_OBS and self.hits / self.obs >= CONFIRM_RATE
            self.status = "confirmed" if confirmed else "hypothesis"

    def to_line(self) -> str:
        tail = f" · miss streak {self.streak}" if self.streak else ""
        return f"- {self.name} — {self.hits}/{self.obs} — {self.status}{tail}"


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def _section_bounds(lines: list[str]) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if line.startswith(SECTION)), None)
    if start is None:
        raise ValueError(f"{SECTION!r} section not found")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def load(path: Path) -> list[Counter]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines)
    counters = []
    for line in lines[start + 1:end]:
        m = LINE_RE.match(line)
        if m:
            counters.append(Counter(m["name"], int(m["hits"]), int(m["obs"]),
                                    m["status"], int(m["streak"] or 0)))
    return counters


def save(path: Path, counters: list[Counter]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines)
    block = [lines[start], FORMAT_NOTE] + [c.to_line() for c in counters]
    tail = lines[end:]
    if tail:
        block.append("")
    path.write_text("\n".join(lines[:start] + block + tail) + "\n", encoding="utf-8")


def apply(path: Path, observations: list[dict]) -> list[Counter]:
    """observations: [{"tendency": str, "hit": bool}]. Returns the counters touched."""
    counters = load(path)
    by_key = {_key(c.name): c for c in counters}
    touched = []
    for obs in observations:
        name = str(obs.get("tendency", "")).strip()
        if not name:
            continue
        counter = by_key.get(_key(name))
        if counter is None:
            counter = Counter(name)
            counters.append(counter)
            by_key[_key(name)] = counter
        counter.record(bool(obs.get("hit")))
        touched.append(counter)
    save(path, counters)
    return touched
