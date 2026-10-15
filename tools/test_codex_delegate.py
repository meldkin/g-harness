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


# ── confinement (--confine) ──────────────────────────────────────────────────


def test_build_plan_confine_wraps_the_launcher(tmp_path):
    mod = _load()
    plan = mod.build_plan(
        "x",
        brief_file=tmp_path / "b",
        out_file=tmp_path / "o",
        powershell="ps",
        confine=True,
        confine_temp=tmp_path / "tmp",
        confine_also_write=[str(tmp_path / "state")],
    )
    argv = list(plan["argv"])  # type: ignore[arg-type]
    assert plan["confined"] is True
    separator = argv.index("--")
    runner = argv[:separator]
    assert runner[0] == sys.executable
    assert runner[1].endswith("win_sandbox.py")
    assert runner[2] == "run"
    assert runner[runner.index("--workspace") + 1] == str(mod.ROOT)
    assert runner[runner.index("--temp") + 1] == str(tmp_path / "tmp")
    assert runner[runner.index("--mode") + 1] == "read-only"
    assert runner[runner.index("--also-write") + 1] == str(tmp_path / "state")
    # The launcher argv is passed through untouched after the separator.
    assert argv[separator + 1] == "ps"
    assert argv[separator + 2] == "-NoProfile"


def test_build_plan_confine_follows_allow_write(tmp_path):
    mod = _load()
    plan = mod.build_plan(
        "x",
        allow_write=True,
        brief_file=tmp_path / "b",
        out_file=tmp_path / "o",
        confine=True,
        confine_temp=tmp_path / "tmp",
    )
    argv = list(plan["argv"])  # type: ignore[arg-type]
    assert argv[argv.index("--mode") + 1] == "workspace-write"
    assert "--also-write" not in argv  # no roots requested, none invented


def test_build_plan_confine_requires_a_temp_dir(tmp_path):
    mod = _load()
    with pytest.raises(ValueError):
        mod.build_plan(
            "x", brief_file=tmp_path / "b", out_file=tmp_path / "o", confine=True
        )


def test_default_confine_roots_tracks_the_codex_state_dir(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "CODEX_STATE_DIR", tmp_path / "absent")
    assert mod.default_confine_roots() == []
    state = tmp_path / ".codex"
    state.mkdir()
    monkeypatch.setattr(mod, "CODEX_STATE_DIR", state)
    assert mod.default_confine_roots() == [str(state)]


def test_main_refuses_also_write_under_read_only(tmp_path, monkeypatch, capsys):
    """read-only grants no writable root, so the flag must not be silently dropped."""
    mod = _load()
    launcher = tmp_path / "codex-env.ps1"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod, "LAUNCHER", launcher)
    monkeypatch.setattr(mod, "_find_powershell", lambda: "ps")
    monkeypatch.setattr(
        mod, "_load_sandbox", lambda: SimpleNamespace(probe=lambda: {"available": True})
    )
    assert mod.main(["do x", "--confine", "--confine-also-write", str(tmp_path)]) == 1
    assert "read-only confinement has no writable root" in capsys.readouterr().err


def test_main_refuses_confine_until_the_hang_is_diagnosed(
    tmp_path, monkeypatch, capsys
):
    """The guard exists because a confined Codex run never returns (plan.md P2.1b)."""
    mod = _load()
    launcher = tmp_path / "codex-env.ps1"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod, "LAUNCHER", launcher)
    monkeypatch.setattr(mod, "_find_powershell", lambda: "ps")
    monkeypatch.setattr(
        mod, "_load_sandbox", lambda: SimpleNamespace(probe=lambda: {"available": True})
    )
    assert mod.main(["do x", "--confine", "--allow-write"]) == 1
    assert "not usable for Codex yet" in capsys.readouterr().err


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


def test_run_plan_falls_back_to_the_transcript(monkeypatch, tmp_path):
    """A read-only confined run cannot write `-o`, so stdout is all that is left."""
    mod = _load()
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="the answer", stderr=""),
    )
    assert mod.run_plan(["x"], tmp_path / "never-written", 5) == (0, "the answer")


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_rejects_non_windows(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod.sys, "platform", "linux")
    assert mod.main(["task"]) == 1
    assert "Windows-only" in capsys.readouterr().err


def test_main_confine_fails_closed_when_the_host_cannot(tmp_path, monkeypatch, capsys):
    """Asked to confine, never fall back to an unconfined worker."""
    mod = _load()
    launcher = tmp_path / "codex-env.ps1"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod, "LAUNCHER", launcher)
    monkeypatch.setattr(mod, "_find_powershell", lambda: "ps")
    monkeypatch.setattr(
        mod,
        "_load_sandbox",
        lambda: SimpleNamespace(
            probe=lambda: {"available": False, "reason": "not Windows"}
        ),
    )
    assert mod.main(["do x", "--confine"]) == 1
    assert "cannot confine" in capsys.readouterr().err


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
