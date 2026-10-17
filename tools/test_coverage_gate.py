"""Tests for tools/coverage_gate.py — per-file coverage ratchet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coverage_gate  # noqa: E402


def test_main_help_flag(monkeypatch, capsys):
    """--help should print docstring usage and exit 0 without running coverage."""
    monkeypatch.setattr(sys, "argv", ["coverage_gate.py", "--help"])
    assert coverage_gate.main() == 0
    out = capsys.readouterr().out
    assert "Coverage Gate" in out
    assert "--update" in out


def test_main_short_help_flag(monkeypatch, capsys):
    """-h should print docstring usage and exit 0 without running coverage."""
    monkeypatch.setattr(sys, "argv", ["coverage_gate.py", "-h"])
    assert coverage_gate.main() == 0
    out = capsys.readouterr().out
    assert "Coverage Gate" in out


def test_load_budget_missing_file(tmp_path):
    """Missing budget file returns an empty dict -- not None.

    The old bare `return` made this None despite the docstring promising an
    empty dict. The test pinned that: it asserted `is None`, so `--report`'s
    `set(budget.keys())` raised AttributeError on a first run and nothing
    caught it.
    """
    result = coverage_gate.load_budget(tmp_path / "nonexistent.json")
    assert result == {}
    assert list(result.keys()) == []


def test_load_budget_valid(tmp_path):
    """Valid budget JSON loads correctly."""
    bfile = tmp_path / "budget.json"
    bfile.write_text(json.dumps({"files": {"tools/deploy.py": 85.5}}), encoding="utf-8")
    loaded = coverage_gate.load_budget(bfile)
    assert loaded == {"tools/deploy.py": 85.5}


def test_load_budget_malformed(tmp_path):
    """Malformed budget JSON raises ValueError."""
    bfile = tmp_path / "budget.json"
    bfile.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed budget file"):
        coverage_gate.load_budget(bfile)


def test_check_ratchet_maintained():
    """Ratchet passes when all files maintain coverage."""
    budget = {"a.py": 80.0, "b.py": 90.0}
    current = {"a.py": 80.0, "b.py": 95.0}
    passed, violations = coverage_gate.check_ratchet(budget, current)
    assert passed is True
    assert violations == []


def test_check_ratchet_decreased():
    """Ratchet fails when coverage drops below budget."""
    budget = {"a.py": 80.0, "b.py": 90.0}
    current = {"a.py": 75.0, "b.py": 90.0}
    passed, violations = coverage_gate.check_ratchet(budget, current)
    assert passed is False
    assert len(violations) == 1
    assert "a.py: 80.0% -> 75.0%" in violations[0]


def test_runtime_copy_without_tests_is_skipped(tmp_path, monkeypatch, capsys):
    """A deployed target has no harness tests, so the baselines cannot apply: skip, do not fail.

    Measured on a real target: 40-odd files reported 0.0% because deploy.py excludes test_*.py by
    policy, and the gate failed while the project was fine.
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "agent_scope.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(coverage_gate, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["coverage_gate.py"])

    assert coverage_gate.main() == 0
    out = capsys.readouterr().out
    assert "[SKIP]" in out
    assert "deployed runtime copy" in out


def test_harness_tests_present_detects_both_checkouts(tmp_path):
    """The guard itself must not fire in this repo, which does ship the tests."""
    assert coverage_gate.harness_tests_present(ROOT) is True
    (tmp_path / "tools").mkdir()
    assert coverage_gate.harness_tests_present(tmp_path) is False
