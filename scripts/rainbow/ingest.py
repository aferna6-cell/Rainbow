"""Track which files in knowledge/opponent/raw/ have been ingested.

The manifest (raw/.ingested, one filename per line) is committed so the
unattended job knows what is new. Raw files themselves are never modified.
"""

from pathlib import Path

from . import paths

MANIFEST = ".ingested"
SKIP = {"README.md", MANIFEST}


def manifest_path() -> Path:
    return paths.raw_dir() / MANIFEST


def ingested() -> set[str]:
    path = manifest_path()
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def pending() -> list[Path]:
    done = ingested()
    return sorted(
        p for p in paths.raw_dir().iterdir()
        if p.is_file() and p.name not in SKIP and not p.name.startswith(".") and p.name not in done
    )


def mark(files: list[Path]) -> None:
    names = sorted(ingested() | {p.name for p in files})
    manifest_path().write_text("\n".join(names) + "\n", encoding="utf-8")
