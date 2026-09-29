"""Commit helper. Commits only the given paths; pushes only when asked."""

import subprocess

from . import paths


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=paths.root(), capture_output=True, text=True)


def commit(message: str, pathspecs: list[str], push: bool = False) -> str:
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return "not a git repo — skipped commit"
    pathspecs = [p for p in pathspecs if (paths.root() / p).exists()]
    if not pathspecs:
        return "nothing to commit"
    _git("add", "--", *pathspecs)
    if _git("diff", "--cached", "--quiet", "--", *pathspecs).returncode == 0:
        return "nothing to commit"
    done = _git("commit", "-m", message, "--", *pathspecs)
    if done.returncode != 0:
        return f"commit failed: {done.stderr.strip()}"
    if push:
        pushed = _git("push")
        return "committed + pushed" if pushed.returncode == 0 else f"committed; push failed: {pushed.stderr.strip()}"
    return "committed"
