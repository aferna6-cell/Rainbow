"""Session journal: data/sessions/YYYY-MM-DD[-N].md (format in data/sessions/README.md).

The table is always the last thing in the file, so rows are appended.
A bans-reset is recorded as a non-numbered row so cumulative bans can be
recomputed from the file alone (a crashed session resumes correctly).
"""

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from . import paths

TABLE_HEADER = (
    "| R | Side | Ban (me) | Ban (him) | My op | His op | W/L | What happened |\n"
    "|---|------|----------|-----------|-------|--------|-----|----------------|\n"
)
SUMMARY_PLACEHOLDER = "Summary: (written at session end)"
RESET_MARKER = "BANS RESET"


@dataclass
class Row:
    round: int
    side: str
    my_ban: str
    his_ban: str
    my_op: str
    his_op: str
    result: str
    what: str

    def to_line(self) -> str:
        cells = [str(self.round), self.side, self.my_ban, self.his_ban,
                 self.my_op, self.his_op, self.result, self.what]
        return "| " + " | ".join(_cell(c) for c in cells) + " |\n"


def _cell(value: str) -> str:
    text = " ".join(str(value or "").split())
    return text.replace("|", "/") or "—"


def session_path(date: dt.date, new: bool = False) -> Path:
    """Today's file; with new=True, the next unused -N suffix."""
    base = paths.sessions_dir() / f"{date.isoformat()}.md"
    if not new:
        latest = base
        n = 2
        while (candidate := base.with_name(f"{date.isoformat()}-{n}.md")).exists():
            latest = candidate
            n += 1
        return latest
    if not base.exists():
        return base
    n = 2
    while (candidate := base.with_name(f"{date.isoformat()}-{n}.md")).exists():
        n += 1
    return candidate


def create(path: Path, date: dt.date, map_name: str, rules: str, opponent: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Session {date.isoformat()} · {map_name} · rules: {rules} · vs {opponent}\n"
        f"{SUMMARY_PLACEHOLDER}\n\n" + TABLE_HEADER,
        encoding="utf-8",
    )


def header(path: Path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0]


def _table_lines(path: Path) -> list[list[str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| R |"):
            continue
        out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out


def rows(path: Path) -> list[Row]:
    result = []
    for cells in _table_lines(path):
        if len(cells) == 8 and cells[0].isdigit():
            result.append(Row(int(cells[0]), *cells[1:]))
    return result


def append_row(path: Path, row: Row) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(row.to_line())


def mark_bans_reset(path: Path) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write("| — | — | — | — | — | — | — | " + RESET_MARKER + " |\n")


def next_round(path: Path) -> int:
    existing = rows(path)
    return existing[-1].round + 1 if existing else 1


def cumulative_bans(path: Path) -> tuple[list[str], list[str]]:
    """Confirmed bans since the last reset: (mine, his)."""
    mine: list[str] = []
    his: list[str] = []
    for cells in _table_lines(path):
        if cells and cells[-1] == RESET_MARKER:
            mine, his = [], []
            continue
        if len(cells) == 8 and cells[0].isdigit():
            if cells[2] != "—":
                mine.append(cells[2])
            if cells[3] != "—":
                his.append(cells[3])
    return mine, his


def score(path: Path) -> tuple[int, int]:
    results = [r.result.upper() for r in rows(path)]
    return results.count("W"), results.count("L")


def write_summary(path: Path, lines: list[str]) -> None:
    """Replace everything between the title line and the table with the summary."""
    text = path.read_text(encoding="utf-8").splitlines(keepends=True)
    table_start = next(i for i, line in enumerate(text) if line.startswith("| R |"))
    body = "Summary:\n" + "".join(f"- {line.strip()}\n" for line in lines) + "\n"
    path.write_text(text[0] + body + "".join(text[table_start:]), encoding="utf-8")


def recent_sessions(exclude: Path | None = None, limit: int = 2) -> list[Path]:
    files = sorted(
        (p for p in paths.sessions_dir().glob("*.md")
         if re.match(r"\d{4}-\d{2}-\d{2}(-\d+)?\.md$", p.name)),
        key=lambda p: (p.name[:10], int(p.stem[11:] or 1)),
    )
    if exclude is not None:
        files = [p for p in files if p.resolve() != exclude.resolve()]
    return files[-limit:]
