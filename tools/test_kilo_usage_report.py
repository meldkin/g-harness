#!/usr/bin/env python3
"""Tests for tools/kilo_usage_report.py — aggregation over the usage JSONL."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "kilo_usage_report.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "kilo_usage_report_under_test", SCRIPT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_entries_missing_file_exits_zero(tmp_path, capsys):
    mod = _load()
    with pytest.raises(SystemExit) as excinfo:
        mod.load_entries(tmp_path / "absent.jsonl")
    assert excinfo.value.code == 0
    assert "No usage log found" in capsys.readouterr().out


def test_load_entries_skips_blank_and_malformed_lines(tmp_path):
    mod = _load()
    p = tmp_path / "u.jsonl"
    p.write_text('{"model": "m"}\n\nnot-json{{\n{"model": "n"}\n', encoding="utf-8")
    assert mod.load_entries(p) == [{"model": "m"}, {"model": "n"}]


def test_main_reports_empty_log(tmp_path, monkeypatch, capsys):
    mod = _load()
    p = tmp_path / "u.jsonl"
    p.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "USAGE_LOG", p)
    mod.main()
    assert "Usage log is empty." in capsys.readouterr().out


def test_main_aggregates_calls_tokens_cost_and_errors(tmp_path, monkeypatch, capsys):
    mod = _load()
    p = tmp_path / "u.jsonl"
    rows = [
        {"model": "a", "usage": {"input": 100, "output": 20}, "cost": 0.5},
        {"model": "a", "usage": {"input": 50, "output": 5}, "cost": 0.25},
        {"model": "b", "error": "boom"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(mod, "USAGE_LOG", p)
    mod.main()
    out = capsys.readouterr().out
    assert "Total calls : 3" in out
    assert "errors: 1" in out
    assert "input=150" in out
    assert "output=25" in out
    assert "$0.750000" in out


def test_error_rows_count_as_calls_but_contribute_no_tokens(
    tmp_path, monkeypatch, capsys
):
    mod = _load()
    p = tmp_path / "u.jsonl"
    p.write_text(
        json.dumps({"model": "x", "error": "e", "usage": {"input": 999}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "USAGE_LOG", p)
    mod.main()
    out = capsys.readouterr().out
    assert "Total calls : 1" in out
    assert "input=0" in out
