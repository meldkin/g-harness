#!/usr/bin/env python3
"""Tests for tools/session_registry.py — the child-session registry (gap G7).

Every test points the registry at tmp_path, so nothing touches `.solocode/`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "session_registry.py"


def _load():
    spec = importlib.util.spec_from_file_location("session_registry_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _dead_pid() -> int:
    """A pid that certainly existed and certainly exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    return int(proc.pid)


def test_record_start_writes_a_running_record(tmp_path):
    mod = _load()
    run_id = mod.record_start(
        "opencode",
        model="commandcode/deepseek-v4.1-flash",
        argv=["opencode", "run"],
        log_path=tmp_path / "run.log",
        session_dir=tmp_path,
    )
    payload = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["worker"] == "opencode"
    assert payload["model"] == "commandcode/deepseek-v4.1-flash"
    assert payload["argv"] == ["opencode", "run"]
    assert payload["pid"] == os.getpid()
    assert payload["state"] == "running"
    assert payload["finished_at"] is None

    sessions = mod.list_sessions(session_dir=tmp_path)
    assert [s["run_id"] for s in sessions] == [run_id]
    assert sessions[0]["state"] == "running"


def test_record_finish_settles_the_record(tmp_path):
    mod = _load()
    run_id = mod.record_start("kilo", session_dir=tmp_path)
    assert mod.record_finish(run_id, 0, session_dir=tmp_path) is True

    settled = mod.list_sessions(session_dir=tmp_path)[0]
    assert settled["state"] == "exited"
    assert settled["exit_code"] == 0
    assert settled["finished_at"] is not None
    assert settled["worker"] == "kilo"  # finish must not clobber the rest


def test_record_finish_on_an_unknown_run_id_is_false(tmp_path):
    mod = _load()
    assert mod.record_finish("nosuchrun", 0, session_dir=tmp_path) is False


def test_a_dead_pid_reports_stale_not_running(tmp_path):
    mod = _load()
    run_id = mod.record_start("codex", pid=_dead_pid(), session_dir=tmp_path)
    session = mod.list_sessions(session_dir=tmp_path)[0]
    assert session["run_id"] == run_id
    assert session["state"] == "stale"


def test_list_skips_a_torn_or_foreign_file(tmp_path):
    mod = _load()
    (tmp_path / "torn.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "foreign.json").write_text('{"hello": 1}', encoding="utf-8")
    assert mod.list_sessions(session_dir=tmp_path) == []


def test_list_is_newest_first(tmp_path, monkeypatch):
    mod = _load()
    stamps = iter(["2026-10-15T00:00:01+00:00", "2026-10-15T00:00:02+00:00"])
    monkeypatch.setattr(mod, "_now", lambda: next(stamps))
    first = mod.record_start("a", session_dir=tmp_path)
    second = mod.record_start("b", session_dir=tmp_path)
    assert [s["run_id"] for s in mod.list_sessions(session_dir=tmp_path)] == [
        second,
        first,
    ]


def test_list_on_a_missing_directory_is_empty(tmp_path):
    mod = _load()
    assert mod.list_sessions(session_dir=tmp_path / "absent") == []


def test_pid_alive_self_dead_child_and_nonsense():
    mod = _load()
    assert mod.pid_alive(os.getpid()) is True
    assert mod.pid_alive(_dead_pid()) is False
    assert mod.pid_alive(0) is False
    assert mod.pid_alive(-1) is False
