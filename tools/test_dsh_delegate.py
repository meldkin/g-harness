#!/usr/bin/env python3
"""Tests for tools/dsh_delegate.py — the DeepSeek Harness (dsh) wrapper."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "dsh_delegate.py"


def _load():
    spec = importlib.util.spec_from_file_location("dsh_delegate_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── load_env_file ────────────────────────────────────────────────────────────


def test_load_env_file_missing_returns_empty(tmp_path):
    assert _load().load_env_file(tmp_path / "nope.env") == {}


def test_load_env_file_parses_and_strips_quotes(tmp_path):
    mod = _load()
    p = tmp_path / ".env"
    p.write_text("# c\nA=1\nB='two'\nC=\"three\"\n\n", encoding="utf-8")
    assert mod.load_env_file(p) == {"A": "1", "B": "two", "C": "three"}


# ── checkout discovery ───────────────────────────────────────────────────────


def test_find_dsh_dir_explicit(tmp_path):
    mod = _load()
    (tmp_path / "packages").mkdir()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert mod.find_dsh_dir(str(tmp_path)) == tmp_path.resolve()


def test_find_dsh_dir_honours_env(tmp_path, monkeypatch):
    mod = _load()
    (tmp_path / "packages").mkdir()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("DSH_DIR", str(tmp_path))
    assert mod.find_dsh_dir(None) == tmp_path.resolve()


def test_find_dsh_dir_returns_none_when_absent(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.delenv("DSH_DIR", raising=False)
    monkeypatch.setattr(mod, "ROOT", tmp_path / "empty-root")
    assert mod.find_dsh_dir(None) is None


def test_dsh_script_declared(tmp_path):
    mod = _load()
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"dsh": "node x"}}), encoding="utf-8"
    )
    assert mod.dsh_script_declared(tmp_path) is True
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {}}), encoding="utf-8"
    )
    assert mod.dsh_script_declared(tmp_path) is False
    (tmp_path / "package.json").write_text("{ not json", encoding="utf-8")
    assert mod.dsh_script_declared(tmp_path) is False


def test_build_command_keeps_the_task_as_one_argument():
    mod = _load()
    assert mod.build_command("pnpm", "headless", "do a thing") == [
        "pnpm",
        "dsh",
        "--profile",
        "headless",
        "do a thing",
    ]
    assert mod.build_command("pnpm", "headless", "a\nb")[-1] == "a\nb"


# ── run_dsh ──────────────────────────────────────────────────────────────────


def test_run_dsh_returns_streams(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="out", stderr=""),
    )
    assert mod.run_dsh(command=["pnpm"], dsh_dir=tmp_path, env={}, timeout_s=5) == (
        0,
        "out",
        "",
    )


def test_run_dsh_timeout_is_124(monkeypatch, tmp_path):
    mod = _load()

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="pnpm", timeout=1)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    code, _out, err = mod.run_dsh(
        command=["pnpm"], dsh_dir=tmp_path, env={}, timeout_s=1
    )
    assert code == 124 and "Timeout" in err


def test_run_dsh_oserror_is_1(monkeypatch, tmp_path):
    mod = _load()

    def boom(*_a, **_k):
        raise OSError("not launchable")

    monkeypatch.setattr(mod.subprocess, "run", boom)
    code, _out, err = mod.run_dsh(
        command=["pnpm"], dsh_dir=tmp_path, env={}, timeout_s=1
    )
    assert code == 1 and "not launchable" in err


# ── self-test / main ─────────────────────────────────────────────────────────


def test_self_test_passes_on_this_machine():
    mod = _load()
    assert mod._self_test() == 0


def test_main_self_test_cli():
    mod = _load()
    assert mod.main(["--self-test"]) == 0


def test_main_requires_a_prompt():
    mod = _load()
    with pytest.raises(SystemExit):
        mod.main([])


def test_main_rejects_nonpositive_timeout():
    mod = _load()
    with pytest.raises(SystemExit):
        mod.main(["task", "--timeout", "0"])


def test_main_returns_one_when_checkout_missing(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: None)
    assert mod.main(["task"]) == 1


def test_main_returns_one_when_no_dsh_script(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: tmp_path)
    monkeypatch.setattr(mod, "dsh_script_declared", lambda _d: False)
    assert mod.main(["task"]) == 1


def test_main_returns_one_when_pnpm_missing(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: tmp_path)
    monkeypatch.setattr(mod, "dsh_script_declared", lambda _d: True)
    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    assert mod.main(["task"]) == 1


def test_main_returns_one_without_api_key(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: tmp_path)
    monkeypatch.setattr(mod, "dsh_script_declared", lambda _d: True)
    monkeypatch.setattr(mod.shutil, "which", lambda _name: "pnpm")
    monkeypatch.setattr(mod, "load_env_file", lambda _p: {})
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert mod.main(["task"]) == 1


def test_main_happy_path(monkeypatch, tmp_path, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: tmp_path)
    monkeypatch.setattr(mod, "dsh_script_declared", lambda _d: True)
    monkeypatch.setattr(mod.shutil, "which", lambda _name: "pnpm")
    monkeypatch.setattr(mod, "load_env_file", lambda _p: {"DEEPSEEK_API_KEY": "k"})
    monkeypatch.setattr(
        mod,
        "run_dsh",
        lambda **_k: (0, "dsh said hello\n", ""),
    )
    assert mod.main(["task", "--profile", "headless"]) == 0
    assert "dsh said hello" in capsys.readouterr().out


def test_main_propagates_nonzero_exit(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "find_dsh_dir", lambda _explicit: tmp_path)
    monkeypatch.setattr(mod, "dsh_script_declared", lambda _d: True)
    monkeypatch.setattr(mod.shutil, "which", lambda _name: "pnpm")
    monkeypatch.setattr(mod, "load_env_file", lambda _p: {"DEEPSEEK_API_KEY": "k"})
    monkeypatch.setattr(mod, "run_dsh", lambda **_k: (7, "", "boom"))
    assert mod.main(["task"]) == 7


# ── encoding safety ──────────────────────────────────────────────────────────


def test_encoding_safe_tolerates_streams_without_reconfigure(monkeypatch):
    mod = _load()

    class Plain:
        pass

    monkeypatch.setattr(mod.sys, "stdout", Plain())
    monkeypatch.setattr(mod.sys, "stderr", Plain())
    mod._make_streams_encoding_safe()  # must not raise


def test_encoding_safe_reconfigures_both_streams(monkeypatch):
    mod = _load()
    calls: list[dict] = []

    class Reconfigurable:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(mod.sys, "stdout", Reconfigurable())
    monkeypatch.setattr(mod.sys, "stderr", Reconfigurable())
    mod._make_streams_encoding_safe()
    assert calls == [{"encoding": "utf-8", "errors": "replace"}] * 2
