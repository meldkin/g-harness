#!/usr/bin/env python3
"""Tests for tools/codex_delegate.py — the Codex (ChatGPT) worker fence."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "codex_delegate.py"


def _load():
    spec = importlib.util.spec_from_file_location("codex_delegate_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── build_plan (the security-relevant part) ──────────────────────────────────


def test_build_plan_is_read_only_by_default(tmp_path):
    mod = _load()
    brief, out = tmp_path / "b.md", tmp_path / "o.md"
    plan = mod.build_plan("do x", brief_file=brief, out_file=out, powershell="ps")
    argv = plan["argv"]
    assert plan["sandbox"] == "read-only"
    assert argv[0] == "ps"
    assert "exec" in argv and "--ephemeral" in argv
    assert argv[argv.index("-s") + 1] == "read-only"
    assert str(out) in argv
    assert str(brief) in argv[-1]
    assert argv[-1].endswith("It is your complete brief.")
    assert plan["brief"].startswith("STRICT OPERATING CONSTRAINTS")
    assert plan["brief"].rstrip().endswith("do x")


def test_build_plan_allow_write_switches_sandbox(tmp_path):
    mod = _load()
    plan = mod.build_plan(
        "x", allow_write=True, brief_file=tmp_path / "b", out_file=tmp_path / "o"
    )
    assert plan["sandbox"] == "workspace-write"


def test_build_plan_model_passthrough(tmp_path):
    mod = _load()
    plan = mod.build_plan(
        "x", model="gpt-6.1-sol", brief_file=tmp_path / "b", out_file=tmp_path / "o"
    )
    argv = plan["argv"]
    assert argv[argv.index("-m") + 1] == "gpt-6.1-sol"


def test_build_plan_never_emits_a_dangerous_flag(tmp_path):
    mod = _load()
    for allow in (False, True):
        joined = " ".join(
            str(a)
            for a in mod.build_plan(
                "x",
                allow_write=allow,
                brief_file=tmp_path / "b",
                out_file=tmp_path / "o",
            )["argv"]
        )
        assert "danger" not in joined
        assert "--dangerously" not in joined


# ── run_plan / change_summary ────────────────────────────────────────────────


def test_change_summary_shape():
    mod = _load()
    assert set(mod.change_summary()) == {"status", "diffstat"}


def test_run_plan_returns_output_and_code(monkeypatch, tmp_path):
    mod = _load()
    out = tmp_path / "o.md"

    def fake(*_a, **_k):
        out.write_text("done", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake)
    assert mod.run_plan(["x"], out, 5) == (0, "done")


def test_run_plan_empty_output_is_exit_two(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert mod.run_plan(["x"], tmp_path / "o", 5)[0] == 2


def test_run_plan_timeout_is_exit_three(monkeypatch, tmp_path):
    mod = _load()

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod.run_plan(["x"], tmp_path / "o", 5)[0] == 3


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_rejects_non_windows(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod.sys, "platform", "linux")
    assert mod.main(["task"]) == 1
    assert "Windows-only" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform != "win32", reason="codex-env.ps1 is Windows-only")
def test_main_dry_run_prints_the_plan(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_find_powershell", lambda: "ps")
    assert mod.main(["do x", "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sandbox"] == "read-only"


@pytest.mark.skipif(sys.platform != "win32", reason="codex-env.ps1 is Windows-only")
def test_main_full_run_with_mocked_plan(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_find_powershell", lambda: "ps")
    monkeypatch.setattr(mod, "run_plan", lambda _argv, _out, _t: (0, "the answer"))
    monkeypatch.setattr(
        mod, "change_summary", lambda root=None: {"status": " M x", "diffstat": ""}
    )
    monkeypatch.setattr(mod, "log_usage", lambda *_a, **_k: None)
    assert mod.main(["do x", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["output"] == "the answer"
    assert payload["changes"]["status"] == " M x"
