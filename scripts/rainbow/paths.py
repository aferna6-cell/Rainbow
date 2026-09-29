"""Repo paths. RAINBOW_ROOT overrides the repo root (used by tests)."""

import os
from pathlib import Path


def root() -> Path:
    env = os.environ.get("RAINBOW_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def sessions_dir() -> Path:
    return root() / "data" / "sessions"


def gio_file() -> Path:
    return root() / "knowledge" / "opponent" / "gio.md"


def meta_file() -> Path:
    return root() / "knowledge" / "meta" / "current-meta.md"


def raw_dir() -> Path:
    return root() / "knowledge" / "opponent" / "raw"
