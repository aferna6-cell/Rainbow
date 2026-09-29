"""Thin wrapper around headless Claude Code (`claude -p --output-format json`).

RAINBOW_CLAUDE_BIN overrides the executable (tests use a fake);
RAINBOW_MODEL picks the model (default: your Claude Code default).
"""

import json
import os
import subprocess
from dataclasses import dataclass

from . import paths

READ_ONLY = ("Read", "Glob", "Grep")


class ClaudeError(RuntimeError):
    pass


@dataclass
class Reply:
    session_id: str | None
    text: str
    data: dict | None
    cost_usd: float


def run(prompt: str, *, schema: dict | None = None, resume: str | None = None,
        tools: tuple[str, ...] = READ_ONLY, timeout: int = 600) -> Reply:
    cmd = [os.environ.get("RAINBOW_CLAUDE_BIN", "claude"), "-p", prompt, "--output-format", "json"]
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    if resume:
        cmd += ["--resume", resume]
    if os.environ.get("RAINBOW_MODEL"):
        cmd += ["--model", os.environ["RAINBOW_MODEL"]]
    try:
        proc = subprocess.run(cmd, cwd=paths.root(), stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ClaudeError(f"Claude Code CLI not found ({cmd[0]}). Install it or set RAINBOW_CLAUDE_BIN.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"claude timed out after {timeout}s") from exc
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"claude exit {proc.returncode}: {(proc.stderr or proc.stdout)[-800:]}") from exc
    if proc.returncode != 0 or out.get("is_error"):
        raise ClaudeError(f"claude error: {str(out.get('result') or proc.stderr)[-800:]}")
    text = out.get("result") or ""
    data = out.get("structured_output")
    if schema is not None and data is None:
        data = _parse_json(text)
    return Reply(out.get("session_id"), text, data, float(out.get("total_cost_usd") or 0))


def _parse_json(text: str) -> dict:
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"expected JSON from claude, got: {text[:400]}") from exc
