#!/usr/bin/env python3
"""Tests for tools/codex_verify.py — gate-runner wiring only; no real gates run."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "codex_verify.py"


def _load():
    spec = importlib.util.spec_from_file_location("codex_verify_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_commands_are_well_formed():
    mod = _load()
    assert mod.COMMANDS
    for command in mod.COMMANDS:
        assert isinstance(command, list) and command
        assert all(isinstance(part, str) for part in command)


def test_commands_include_the_documented_gates():
    mod = _load()
    joined = [" ".join(c) for c in mod.COMMANDS]
    assert any("security_scan.py" in c for c in joined)
    assert any("validate_schemas.py" in c for c in joined)
    assert any("garden.py" in c for c in joined)
    assert any("check_skips.py" in c for c in joined)
    assert any("pytest" in c for c in joined)


def test_main_returns_zero_when_every_gate_passes(monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0)
    )
    assert mod.main() == 0


def test_main_stops_and_propagates_first_failure(monkeypatch):
    mod = _load()
    seen = {"n": 0}

    def fake_run(*a, **k):
        seen["n"] += 1
        return SimpleNamespace(returncode=7 if seen["n"] == 2 else 0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod.main() == 7
    assert seen["n"] == 2  # the third and later gates were never reached


def test_main_returns_one_on_timeout(monkeypatch):
    mod = _load()

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=900)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod.main() == 1
