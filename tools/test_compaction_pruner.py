#!/usr/bin/env python3
"""Tests for tools/compaction_pruner.py — byte-budget pruning."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "compaction_pruner.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "compaction_pruner_under_test", SCRIPT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_empty_and_under_budget_pass_through():
    mod = _load()
    assert mod.prune("", 100) == ""
    assert mod.prune("abc", 3) == "abc"
    assert mod.prune("abc", 4) == "abc"
    assert mod.prune("abc", 0) == "abc"  # non-positive budget means "no pruning"


def test_over_budget_respects_budget_and_keeps_the_tail():
    mod = _load()
    out = mod.prune("x" * 1000, 100)
    assert len(out.encode("utf-8")) <= 100
    assert out.endswith("x")  # the tail survives
    assert mod.MARKER.strip() in out


def test_multibyte_is_measured_in_bytes_and_stays_valid_utf8():
    mod = _load()
    out = mod.prune("éééé", 6)  # 4 chars, 8 bytes
    assert len(out.encode("utf-8")) <= 6
    out.encode("utf-8").decode("utf-8")  # valid UTF-8, no split codepoint


def test_tiny_budget_falls_back_to_a_hard_cut():
    mod = _load()
    assert len(mod.prune("abcdef", 3).encode("utf-8")) <= 3


def test_pruning_is_idempotent():
    mod = _load()
    once = mod.prune("y" * 1000, 100)
    assert mod.prune(once, 100) == once


def test_cut_helpers():
    mod = _load()
    assert mod._cut_to_fit("abc", 10) == "abc"
    assert mod._cut_to_fit("abc", 0) == ""
    assert mod._cut_tail_to_fit("abc", 10) == "abc"
    assert mod._cut_tail_to_fit("abc", 0) == ""
    assert mod._cut_tail_to_fit("abcdef", 3) == "def"


def test_self_test_helper_runs():
    _load()._self_test()


def test_cli_self_test():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],  # noqa: S603 — fixed argv
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "All tests passed." in result.stdout


def test_cli_text_under_budget_passes_through(capsys, monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        sys, "argv", ["compaction_pruner.py", "--text", "small", "--bytes", "50"]
    )
    assert mod.main() == 0
    assert capsys.readouterr().out == "small"


def test_cli_text_over_budget_is_pruned(capsys, monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        sys, "argv", ["compaction_pruner.py", "--text", "z" * 500, "--bytes", "40"]
    )
    assert mod.main() == 0
    captured = capsys.readouterr()
    assert len(captured.out.encode("utf-8")) <= 40
    assert "byte budget" in captured.err
