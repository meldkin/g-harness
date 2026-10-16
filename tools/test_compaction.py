#!/usr/bin/env python3
"""Tests for tools/compaction.py — the budget policy, no model required."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "compaction.py"


def _load():
    spec = importlib.util.spec_from_file_location("compaction_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations via sys.modules[cls.__module__];
    # without registering the module that lookup is None and the dataclass breaks.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_unbounded_budget_accepts_everything():
    mod = _load()
    assert mod.Budget().exceeds("") == (False, "")
    assert mod.Budget().exceeds("anything at all") == (False, "")


def test_empty_text_never_exceeds_a_bounded_budget():
    mod = _load()
    assert mod.Budget(char_limit=0).exceeds("") == (False, "")
    assert mod.Budget(byte_limit=0).exceeds("") == (False, "")


def test_char_limit_is_off_by_one_correct():
    mod = _load()
    assert mod.Budget(char_limit=5).exceeds("hello") == (False, "")
    exceeded, reason = mod.Budget(char_limit=5).exceeds("hello!")
    assert exceeded is True
    assert "char budget" in reason


def test_byte_limit_counts_utf8_bytes_not_characters():
    mod = _load()
    assert mod.Budget(byte_limit=2).exceeds("é") == (False, "")  # "é" is 2 UTF-8 bytes
    exceeded, reason = mod.Budget(byte_limit=2).exceeds("é!")  # 3 bytes
    assert exceeded is True
    assert "byte budget" in reason


def test_byte_limit_is_reported_before_char_limit():
    mod = _load()
    exceeded, reason = mod.Budget(char_limit=10, byte_limit=1).exceeds("é")
    assert exceeded is True
    assert "byte budget" in reason


def test_self_test_helper_runs_clean():
    _load()._self_test()


def test_cli_self_test_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],  # noqa: S603 — fixed argv, no shell
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "All tests passed." in result.stdout


def test_cli_without_args_prints_help_and_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],  # noqa: S603 — fixed argv, no shell
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "compaction budget policy" in result.stdout.lower()
