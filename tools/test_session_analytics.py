#!/usr/bin/env python3
"""Tests for tools/session_analytics.py — analytics over a throwaway sessions.db."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "session_analytics.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "session_analytics_under_test", SCRIPT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def seeded(tmp_path):
    """A temp DB with two sessions: one completed (main), one active (feature/x)."""
    mod = _load()
    db = tmp_path / "sessions.db"
    sp = mod.sp
    sp.record_session_start("t1", "main", "abc1234", path=db)
    sp.record_session_start("t2", "feature/x", "def5678", path=db)
    sp.record_session_end("t1", 3, "completed", path=db)
    return mod, db


# ── small helpers ────────────────────────────────────────────────────────────


def test_parse_iso_variants():
    mod = _load()
    assert mod._parse_iso(None) is None
    assert mod._parse_iso("") is None
    assert mod._parse_iso("nonsense") is None
    assert mod._parse_iso("2026-10-07T10:00:00Z") is not None


def test_duration_seconds():
    mod = _load()
    assert mod._duration_seconds("2026-10-07T10:00:00Z", None) is None
    assert mod._duration_seconds("2026-10-07T10:00:00Z", "bad") is None
    assert (
        mod._duration_seconds("2026-10-07T10:00:00Z", "2026-10-07T10:02:00Z") == 120.0
    )


def test_format_duration():
    mod = _load()
    assert mod._format_duration(45) == "45s"
    assert mod._format_duration(120) == "2m"
    assert mod._format_duration(3665) == "1h 1m"


# ── aggregate stats ──────────────────────────────────────────────────────────


def test_overall_stats_on_empty_db(tmp_path):
    mod = _load()
    stats = mod.overall_stats(path=tmp_path / "empty.db")
    assert stats == {
        "total": 0,
        "by_status": {},
        "duration": {},
        "files_changed": {},
        "top_branches": [],
    }


def test_overall_stats_concrete(seeded):
    mod, db = seeded
    stats = mod.overall_stats(path=db)
    assert stats["total"] == 2
    assert stats["by_status"] == {"completed": 1, "active": 1}
    assert stats["files_changed"]["avg"] == 1.5
    assert stats["files_changed"]["max"] == 3
    assert len(stats["top_branches"]) == 2
    assert stats["duration"]  # the completed session contributed a duration


def test_by_branch_stats_concrete(seeded):
    mod, db = seeded
    branch = mod.by_branch_stats(path=db)
    assert branch["main"]["count"] == 1
    assert branch["main"]["completed"] == 1
    assert branch["feature/x"]["active"] == 1
    assert branch["main"]["avg_files_changed"] == 3


def test_by_status_stats_concrete(seeded):
    mod, db = seeded
    status = mod.by_status_stats(path=db)
    assert status["completed"]["count"] == 1
    assert status["completed"]["total_files_changed"] == 3
    assert status["active"]["count"] == 1


def test_recent_sessions_detail(seeded):
    mod, db = seeded
    recent = mod.recent_sessions_detail(5, path=db)
    assert len(recent) == 2
    by_status = {r["status"]: r for r in recent}
    assert by_status["active"]["duration"] == "active"
    assert by_status["completed"]["commit"] == "abc1234"[:7]
    assert by_status["completed"]["files_changed"] == 3


# ── printers ─────────────────────────────────────────────────────────────────


def test_print_stats_full(capsys):
    mod = _load()
    mod.print_stats(
        {
            "total": 3,
            "by_status": {"completed": 2, "active": 1},
            "duration": {"avg": 120, "median": 90, "max": 300},
            "files_changed": {"avg": 2.5, "median": 2, "max": 5},
            "top_branches": [("main", 2), ("fix/x", 1)],
        }
    )
    out = capsys.readouterr().out
    assert "Sessions: 3 total" in out
    assert "Top branches: main (2)" in out


def test_print_stats_minimal(capsys):
    mod = _load()
    mod.print_stats(
        {
            "total": 0,
            "by_status": {},
            "duration": {},
            "files_changed": {"avg": 0.0, "median": 0, "max": 0},
            "top_branches": [],
        }
    )
    assert "Sessions: 0 total" in capsys.readouterr().out


def test_print_by_branch_and_status(capsys):
    mod = _load()
    mod.print_by_branch(
        {
            "main": {
                "count": 2,
                "completed": 1,
                "active": 1,
                "avg_files_changed": 1.5,
                "avg_duration": None,
            }
        }
    )
    mod.print_by_status(
        {"completed": {"count": 1, "total_files_changed": 3, "branches": 1}}
    )
    out = capsys.readouterr().out
    assert "main:" in out and "completed:" in out


def test_print_recent(capsys):
    mod = _load()
    mod.print_recent(
        [
            {
                "start": "2026-10-07T10:00:00Z",
                "duration": "2m",
                "branch": "main",
                "commit": "abc1234",
                "files_changed": 3,
                "status": "completed",
            }
        ]
    )
    assert "main@abc1234" in capsys.readouterr().out


# ── self-test / main ─────────────────────────────────────────────────────────


def test_run_self_test_passes():
    assert _load().run_self_test() is True


def test_main_self_test(monkeypatch):
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["session_analytics.py", "--self-test"])
    assert mod.main() == 0


def test_main_no_args_prints_help(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["session_analytics.py"])
    assert mod.main() == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_main_stats_json(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "overall_stats", lambda path=None: {"total": 1})
    monkeypatch.setattr(sys, "argv", ["session_analytics.py", "--stats", "--json"])
    assert mod.main() == 0
    assert json.loads(capsys.readouterr().out) == {"total": 1}


def test_main_branch_status_recent_json(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(
        mod, "by_branch_stats", lambda path=None: {"main": {"count": 1}}
    )
    monkeypatch.setattr(
        mod, "by_status_stats", lambda path=None: {"completed": {"count": 1}}
    )
    monkeypatch.setattr(
        mod, "recent_sessions_detail", lambda n, path=None: [{"id": "x"}]
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "session_analytics.py",
            "--by-branch",
            "--by-status",
            "--recent",
            "3",
            "--json",
        ],
    )
    assert mod.main() == 0
    # three JSON documents are emitted, one per requested view
    assert capsys.readouterr().out.count("{") >= 3


def test_main_reports_errors(monkeypatch, capsys):
    mod = _load()

    def boom(path=None):
        raise RuntimeError("db is gone")

    monkeypatch.setattr(mod, "overall_stats", boom)
    monkeypatch.setattr(sys, "argv", ["session_analytics.py", "--stats"])
    assert mod.main() == 1
    assert "Error: db is gone" in capsys.readouterr().err
