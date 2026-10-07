#!/usr/bin/env python3
"""Tests for tools/solocode_config.py — env parsing, model resolution, logging."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "solocode_config.py"


def _load():
    spec = importlib.util.spec_from_file_location("solocode_config_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_env(root: Path, body: str) -> None:
    (root / ".env").write_text(body, encoding="utf-8")


def test_load_api_key_reads_and_strips_quotes(tmp_path):
    mod = _load()
    _write_env(tmp_path, 'DEEPSEEK_API_KEY="sk-abc123"\n')
    assert mod.load_api_key(tmp_path) == "sk-abc123"


def test_load_api_key_ignores_comments_and_blanks(tmp_path):
    mod = _load()
    _write_env(tmp_path, "# a comment\n\nDEEPSEEK_API_KEY=plain\n")
    assert mod.load_api_key(tmp_path) == "plain"


def test_load_api_key_treats_placeholder_as_absent(tmp_path):
    mod = _load()
    _write_env(tmp_path, "DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY_HERE\n")
    assert mod.load_api_key(tmp_path) == ""


def test_load_api_key_missing_file_is_empty(tmp_path):
    mod = _load()
    assert mod.load_api_key(tmp_path) == ""


def test_require_api_key_exits_one_when_absent(tmp_path, capsys):
    mod = _load()
    with pytest.raises(SystemExit) as excinfo:
        mod.require_api_key(tmp_path)
    assert excinfo.value.code == 1
    assert "DEEPSEEK_API_KEY not configured" in capsys.readouterr().err


def test_resolve_model_pro():
    mod = _load()
    assert mod.resolve_model("", "pro") == ("deepseek-v4-pro[1m]", "PRO", False)


def test_resolve_model_auto_sets_flag():
    mod = _load()
    name, label, auto = mod.resolve_model("anything", "auto")
    assert name == "deepseek-v4-pro[1m]"
    assert label == "PRO"
    assert auto is True


def test_resolve_model_flash_is_a_deprecated_alias(capsys):
    mod = _load()
    assert mod.resolve_model("", "flash")[0] == "deepseek-v4-pro[1m]"
    assert "deprecated" in capsys.readouterr().err


def test_resolve_model_unknown_exits(capsys):
    mod = _load()
    with pytest.raises(SystemExit) as excinfo:
        mod.resolve_model("", "bogus")
    assert excinfo.value.code == 1
    assert "Unknown model" in capsys.readouterr().err


def test_get_env_vars_wires_key_and_model():
    mod = _load()
    env = mod.get_env_vars("k", "deepseek-v4-pro[1m]")
    assert env["ANTHROPIC_API_KEY"] == "k"
    # Compared to the sibling key rather than a literal: a bare string literal
    # beside a `*_TOKEN` name trips ruff's hardcoded-password rule (S105).
    assert env["ANTHROPIC_AUTH_TOKEN"] == env["ANTHROPIC_API_KEY"]
    assert env["ANTHROPIC_MODEL"] == "deepseek-v4-pro[1m]"
    assert env["ANTHROPIC_BASE_URL"].startswith("https://")


def test_log_session_appends_one_json_line_per_call(tmp_path):
    mod = _load()
    log = tmp_path / "nested" / "usage.log"
    mod.log_session("deepseek-v4-pro[1m]", 12.5, 0, "manual", log_path=log)
    mod.log_session("deepseek-v4-pro[1m]", 1.0, 1, "auto", log_path=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["model"] == "deepseek-v4-pro[1m]"
    assert first["duration_min"] == 12.5
    assert first["exit_code"] == 0
    assert first["mode"] == "manual"


def test_cmd_env_json_labels_the_tier(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "require_api_key", lambda root=None: "k")
    assert mod._cmd_env_json("pro") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["SOLOCODE_MODEL_LABEL"] == "PRO"
    assert payload["SOLOCODE_AUTO_DETECTED"] == "false"


def test_cmd_env_bash_prints_key_value_lines(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "require_api_key", lambda root=None: "k")
    assert mod._cmd_env_bash("pro") == 0
    out = capsys.readouterr().out
    assert "ANTHROPIC_MODEL=deepseek-v4-pro[1m]" in out


def test_cli_resolve_model_prints_canonical_name():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "resolve-model", "some", "text"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "deepseek-v4-pro[1m]"


def test_cli_no_command_prints_help_and_exits_one():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 1
