"""Tests for scripts/rainbow. Run: python3 -m unittest discover -s tests"""

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from rainbow import counters, ingest, journal, maintenance, meta, play  # noqa: E402

TODAY = dt.date(2026, 9, 29)


class RepoCase(unittest.TestCase):
    """Each test runs against a throwaway copy of knowledge/ + data/ in a git repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for sub in ("knowledge", "data"):
            shutil.copytree(REPO / sub, self.tmp / sub)
        self.log = self.tmp / "claude.log"
        self.env = {"RAINBOW_ROOT": str(self.tmp),
                    "RAINBOW_CLAUDE_BIN": str(REPO / "tests" / "fake_claude.py"),
                    "FAKE_CLAUDE_LOG": str(self.log)}
        self._old = {k: os.environ.get(k) for k in list(self.env) + ["FAKE_CLAUDE_FAIL", "FAKE_CLAUDE_SKIP_META_WRITE"]}
        os.environ.update(self.env)
        for key in ("FAKE_CLAUDE_FAIL", "FAKE_CLAUDE_SKIP_META_WRITE"):
            os.environ.pop(key, None)
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        subprocess.run(git + ["add", "."], cwd=self.tmp, check=True)
        subprocess.run(git + ["commit", "-qm", "init"], cwd=self.tmp, check=True)
        os.environ.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []


class CounterRules(unittest.TestCase):
    def test_confirms_at_60_percent_over_5(self):
        c = counters.Counter("x")
        for hit in (True, True, False, True):
            c.record(hit)
        self.assertEqual(c.status, "hypothesis")  # 3/4 — too few obs
        c.record(False)
        self.assertEqual((c.hits, c.obs, c.status), (3, 5, "confirmed"))

    def test_two_consecutive_misses_break(self):
        c = counters.Counter("x", hits=5, obs=5, status="confirmed")
        c.record(False)
        self.assertEqual(c.status, "confirmed")
        c.record(False)
        self.assertEqual(c.status, "broken")
        c.record(False)
        self.assertEqual(c.status, "broken")
        c.record(True)  # 6/8 = 75%, streak cleared
        self.assertEqual((c.status, c.streak), ("confirmed", 0))

    def test_line_roundtrip(self):
        c = counters.Counter("hides off-site", 2, 3, "hypothesis", 1)
        m = counters.LINE_RE.match(c.to_line())
        self.assertEqual((m["name"], m["hits"], m["obs"], m["streak"]), ("hides off-site", "2", "3", "1"))


class Files(RepoCase):
    def test_counters_apply_matches_names_case_insensitively(self):
        gio = self.tmp / "knowledge/opponent/gio.md"
        counters.apply(gio, [{"tendency": "Bans what beat him", "hit": True}])
        counters.apply(gio, [{"tendency": "bans  WHAT beat him", "hit": True}, {"tendency": "", "hit": True}])
        loaded = counters.load(gio)
        self.assertEqual([(c.name, c.hits, c.obs) for c in loaded], [("Bans what beat him", 2, 2)])
        text = gio.read_text()
        self.assertIn("## Constraints", text)  # rest of the file untouched
        self.assertTrue(text.index("## Constraints") < text.index("## Live counters"))

    def test_journal_rows_bans_reset_and_summary(self):
        path = journal.session_path(TODAY)
        journal.create(path, TODAY, "Oregon", "bomb", "Gio")
        journal.append_row(path, journal.Row(1, "DEF", "Fuze", "Mute", "Mozzie", "Ash", "W", "a | b"))
        journal.append_row(path, journal.Row(2, "ATK", "", "Ace", "Maverick", "?", "L", "lost"))
        self.assertEqual(journal.cumulative_bans(path), (["Fuze"], ["Mute", "Ace"]))
        journal.mark_bans_reset(path)
        journal.append_row(path, journal.Row(3, "DEF", "Grim", "", "Smoke", "Fuze", "W", "ok"))
        self.assertEqual(journal.cumulative_bans(path), (["Grim"], []))
        self.assertEqual(journal.next_round(path), 4)
        self.assertEqual(journal.score(path), (2, 1))
        self.assertEqual(journal.rows(path)[0].what, "a / b")
        journal.write_summary(path, ["2-1", "b", "c", "d", "e"])
        self.assertEqual(len(journal.rows(path)), 3)
        self.assertIn("- 2-1\n", path.read_text())

    def test_session_path_suffixes(self):
        first = journal.session_path(TODAY)
        self.assertEqual(first.name, "2026-09-29.md")
        journal.create(first, TODAY, "Oregon", "bomb", "Gio")
        self.assertEqual(journal.session_path(TODAY).name, "2026-09-29.md")
        second = journal.session_path(TODAY, new=True)
        self.assertEqual(second.name, "2026-09-29-2.md")
        journal.create(second, TODAY, "Oregon", "bomb", "Gio")
        self.assertEqual(journal.session_path(TODAY).name, "2026-09-29-2.md")
        self.assertEqual([p.name for p in journal.recent_sessions(exclude=second)], ["2026-09-29.md"])

    def test_meta_staleness(self):
        path = self.tmp / "knowledge/meta/current-meta.md"
        self.assertEqual(meta.last_verified(path), dt.date(2026, 8, 27))
        self.assertFalse(meta.is_stale(path, dt.date(2026, 9, 17)))
        self.assertTrue(meta.is_stale(path, dt.date(2026, 9, 18)))
        self.assertTrue(meta.is_stale(self.tmp / "missing.md", TODAY))

    def test_ingest_manifest(self):
        self.assertEqual(ingest.pending(), [])  # the 2026-08-27 export is already ingested
        new = self.tmp / "knowledge/opponent/raw/notes.md"
        new.write_text("gio went Laundry again")
        (self.tmp / "knowledge/opponent/raw/clip.bin").write_bytes(b"\0")
        out = maintenance.run_ingest()
        self.assertIn("ingested 1/2", out)
        self.assertIn("skipped clip.bin", out)
        self.assertEqual([p.name for p in ingest.pending()], ["clip.bin"])


class Maintenance(RepoCase):
    def test_refresh_only_when_stale_and_verifies_stamp(self):
        self.assertIn("meta fresh", maintenance.refresh_meta(dt.date(2026, 9, 1)))
        self.assertEqual(self.calls(), [])
        self.assertIn("meta refreshed", maintenance.refresh_meta(TODAY))
        self.assertEqual(meta.last_verified(self.tmp / "knowledge/meta/current-meta.md"), TODAY)
        self.assertIn("WebSearch", self.calls()[0]["args"][self.calls()[0]["args"].index("--allowedTools") + 1])

    def test_refresh_fails_loudly_if_file_not_stamped(self):
        os.environ["FAKE_CLAUDE_SKIP_META_WRITE"] = "1"
        with self.assertRaises(Exception):
            maintenance.refresh_meta(TODAY)

    def test_auto_commits_upkeep(self):
        code, log = maintenance.auto(TODAY, push=False)
        self.assertEqual(code, 0, log)
        msg = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=self.tmp, capture_output=True, text=True).stdout
        self.assertEqual(msg.strip(), "auto 2026-09-29: meta/ingest upkeep")


class PlayLoop(RepoCase):
    def run_session(self, lines, **overrides):
        args = types.SimpleNamespace(date=TODAY.isoformat(), map="Oregon", rules="bomb, cumulative bans",
                                     opponent="Gio", first_side="def", new=False, skip_maintenance=True,
                                     no_commit=False, push=False)
        vars(args).update(overrides)
        feed = iter(lines)

        def inp():
            try:
                return next(feed)
            except StopIteration:
                raise EOFError

        out = io.StringIO()
        code = play.run(args, out, inp)
        return code, out.getvalue()

    def test_full_session(self):
        code, out = self.run_session(["ban Fuze", "hisban Mute", "w — pests caught his drone",
                                      "what if he goes Fuze?", "done"])
        self.assertEqual(code, 0, out)
        path = self.tmp / "data/sessions/2026-09-29.md"
        rows = journal.rows(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].my_ban, rows[0].his_ban, rows[0].my_op, rows[0].result), ("Fuze", "Mute", "Mozzie", "W"))
        self.assertIn("── ROUND 2 · Attack ──", out)
        self.assertIn("answer: hold Supply offset", out)
        names = {c.name: c for c in counters.load(self.tmp / "knowledge/opponent/gio.md")}
        self.assertEqual(names["Attacks Basement via Laundry"].hits, 1)
        self.assertEqual(names["bans what beat him last"].streak, 1)
        calls = self.calls()
        self.assertIsNone(calls[0]["resume"])  # session start is a fresh conversation
        self.assertTrue(all(c["resume"] == "sess-1" for c in calls[1:]))  # every later call resumes it
        self.assertIn("me=Fuze, him=Mute", calls[1]["prompt"])
        self.assertIn("- 1-0", path.read_text())
        msg = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=self.tmp, capture_output=True, text=True).stdout
        self.assertEqual(msg.strip(), "session 2026-09-29: 1-0, notes + model update")

    def test_player_result_overrides_model_and_bans_not_carried(self):
        self.run_session(["ban Fuze", "l he flanked me", "l", "quit"])
        rows = journal.rows(self.tmp / "data/sessions/2026-09-29.md")
        self.assertEqual([(r.result, r.my_ban) for r in rows], [("L", "Fuze"), ("L", "—")])

    def test_resume_continues_round_numbers_and_conversation(self):
        self.run_session(["w", "quit"])
        self.run_session(["w", "quit"])
        rows = journal.rows(self.tmp / "data/sessions/2026-09-29.md")
        self.assertEqual([r.round for r in rows], [1, 2])
        starts = [c for c in self.calls() if "Session start" in c["prompt"]]
        self.assertIn("RESUMING 2026-09-29.md at round 2", starts[1]["prompt"])
        self.assertEqual(starts[1]["resume"], "sess-1")

    def test_claude_failure_logs_nothing(self):
        self.run_session(["quit"])
        os.environ["FAKE_CLAUDE_FAIL"] = "1"
        code, out = self.run_session(["w"])
        self.assertEqual(code, 1)
        self.assertIn("could not start coach", out)
        self.assertEqual(journal.rows(self.tmp / "data/sessions/2026-09-29.md"), [])

    def test_questions_not_mistaken_for_results(self):
        self.assertIsNone(play.RESULT_RE.match("where is laundry"))
        self.assertIsNone(play.RESULT_RE.match("lol"))
        self.assertEqual(play.RESULT_RE.match("L - he hid")["rest"], "he hid")
        self.assertEqual(play.RESULT_RE.match("w")["wl"], "w")


if __name__ == "__main__":
    unittest.main()
