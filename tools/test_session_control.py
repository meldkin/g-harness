#!/usr/bin/env python3
"""Tests for tools/session_control.py — list / send / interrupt (gap G7).

The interrupt tests spawn real processes: a child that itself spawns a grandchild,
so a kill that only reaches the direct child is visible as a surviving grandchild.
Every spawned process is cleaned up in a `finally`, so a failing assertion cannot
leave a sleeper behind.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "session_control.py"
REGISTRY = Path(__file__).resolve().parent / "session_registry.py"

_SLEEP_CHILD = (
    "import subprocess, sys, time\n"
    "grand = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "open(sys.argv[1], 'w', encoding='utf-8').write(str(grand.pid))\n"
    "time.sleep(120)\n"
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mods():
    registry = _load("session_registry_for_control", REGISTRY)
    control = _load("session_control_under_test", SCRIPT)
    return registry, control


def _spawn_sleeper_tree(pid_file: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-c", _SLEEP_CHILD, str(pid_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not pid_file.is_file():
        time.sleep(0.05)
    assert pid_file.is_file(), "the child never reported its grandchild pid"
    return proc


def _force_cleanup(control, pids: list[int]) -> None:
    for pid in pids:
        if pid and control.session_registry.pid_alive(pid):
            with contextlib.suppress(OSError, ValueError):
                control.kill_tree(pid)


# ── list ─────────────────────────────────────────────────────────────────────


def test_list_returns_every_recorded_session(mods, tmp_path):
    registry, control = mods
    registry.record_start("opencode", session_dir=tmp_path)
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--session-dir", str(tmp_path), "list"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    payload = json.loads(out.stdout)
    assert out.returncode == 0
    assert len(payload) == 1
    assert payload[0]["worker"] == "opencode"


# ── interrupt ────────────────────────────────────────────────────────────────


def test_interrupt_kills_the_whole_tree(mods, tmp_path):
    registry, control = mods
    pid_file = tmp_path / "grandchild.pid"
    proc = _spawn_sleeper_tree(pid_file)
    grandchild = int(pid_file.read_text(encoding="utf-8").strip())
    run_id = registry.record_start("fake", pid=proc.pid, session_dir=tmp_path)
    try:
        assert control.session_registry.pid_alive(proc.pid) is True
        assert control.session_registry.pid_alive(grandchild) is True

        result = control.interrupt(run_id, session_dir=tmp_path)

        assert result["killed"] is True
        assert control.session_registry.pid_alive(proc.pid) is False
        assert control.session_registry.pid_alive(grandchild) is False
        settled = registry.list_sessions(session_dir=tmp_path)[0]
        assert settled["state"] == "interrupted"
    finally:
        _force_cleanup(control, [proc.pid, grandchild])


def test_interrupt_reports_an_already_exited_session(mods, tmp_path):
    registry, control = mods
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    run_id = registry.record_start("fake", pid=proc.pid, session_dir=tmp_path)

    result = control.interrupt(run_id, session_dir=tmp_path)
    assert result["killed"] is False
    assert result["reason"] == "already exited"
    assert registry.list_sessions(session_dir=tmp_path)[0]["state"] == "exited"


def test_interrupt_unknown_run_id_is_reported(mods, tmp_path):
    _, control = mods
    result = control.interrupt("nosuchrun", session_dir=tmp_path)
    assert result["killed"] is False
    assert result["error"] == "unknown run id"


def test_kill_tree_refuses_the_controller_and_nonsense(mods):
    _, control = mods
    for pid in (os.getpid(), 0, 1, -5):
        with pytest.raises(ValueError):
            control.kill_tree(pid)


# ── send_message ─────────────────────────────────────────────────────────────


def test_send_message_is_unsupported_without_a_channel(mods, tmp_path):
    registry, control = mods
    run_id = registry.record_start("codex", pid=os.getpid(), session_dir=tmp_path)
    result = control.send_message(run_id, "do more", session_dir=tmp_path)
    assert result["status"] == "unsupported"
    assert result["delivered"] is False


def test_send_message_appends_to_a_declared_inbox(mods, tmp_path):
    registry, control = mods
    inbox = tmp_path / "inbox" / "run.txt"
    run_id = registry.record_start(
        "fake",
        pid=os.getpid(),
        channel="file",
        inbox_path=inbox,
        session_dir=tmp_path,
    )
    assert control.send_message(run_id, "first", session_dir=tmp_path)["delivered"]
    assert control.send_message(run_id, "second\n", session_dir=tmp_path)["delivered"]
    assert inbox.read_text(encoding="utf-8") == "first\nsecond\n"


def test_send_message_to_a_settled_session_is_refused(mods, tmp_path):
    registry, control = mods
    inbox = tmp_path / "inbox.txt"
    run_id = registry.record_start(
        "fake", pid=os.getpid(), channel="file", inbox_path=inbox, session_dir=tmp_path
    )
    registry.record_finish(run_id, 0, session_dir=tmp_path)
    result = control.send_message(run_id, "late", session_dir=tmp_path)
    assert result["delivered"] is False
    assert result["status"] == "session is exited"
    assert not inbox.exists()


# ── CLI wiring ───────────────────────────────────────────────────────────────


def test_cli_send_exits_two_when_unsupported(mods, tmp_path):
    registry, _ = mods
    run_id = registry.record_start("codex", pid=os.getpid(), session_dir=tmp_path)
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--session-dir",
            str(tmp_path),
            "send",
            run_id,
            "x",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 2
    assert json.loads(out.stdout)["status"] == "unsupported"


# The CLI test above runs in a child process, which coverage cannot see. These
# call main() in-process so the dispatch branches are measured too.


def test_main_list_in_process(mods, tmp_path, capsys):
    registry, control = mods
    registry.record_start("kilo", session_dir=tmp_path)
    assert control.main(["--session-dir", str(tmp_path), "list"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["worker"] == "kilo"


def test_main_send_in_process_is_exit_two(mods, tmp_path, capsys):
    registry, control = mods
    run_id = registry.record_start("codex", pid=os.getpid(), session_dir=tmp_path)
    assert control.main(["--session-dir", str(tmp_path), "send", run_id, "x"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "unsupported"


def test_main_interrupt_in_process(mods, tmp_path, capsys):
    registry, control = mods
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    run_id = registry.record_start("fake", pid=proc.pid, session_dir=tmp_path)
    assert control.main(["--session-dir", str(tmp_path), "interrupt", run_id]) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "already exited"


def test_main_without_a_command_prints_help(mods, capsys):
    _, control = mods
    assert control.main([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


# ── error branches ───────────────────────────────────────────────────────────


def test_send_message_unknown_run_id(mods, tmp_path):
    _, control = mods
    result = control.send_message("nosuchrun", "x", session_dir=tmp_path)
    assert result["status"] == "unknown run id"
    assert result["delivered"] is False


def test_send_message_reports_a_write_failure(mods, tmp_path):
    registry, control = mods
    run_id = registry.record_start(
        "fake",
        pid=os.getpid(),
        channel="file",
        inbox_path=tmp_path,  # a directory: opening it for append must fail
        session_dir=tmp_path,
    )
    result = control.send_message(run_id, "x", session_dir=tmp_path)
    assert result["delivered"] is False
    assert str(result["status"]).startswith("write failed")


def test_interrupt_reports_a_record_without_a_pid(mods, tmp_path):
    _, control = mods
    run_id = "nopidrun"
    (tmp_path / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "worker": "fake", "pid": "not-an-int"}),
        encoding="utf-8",
    )
    result = control.interrupt(run_id, session_dir=tmp_path)
    assert result["killed"] is False
    assert result["error"] == "record carries no pid"


def test_wait_for_exit_times_out_on_a_live_process(mods):
    _, control = mods
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert control.wait_for_exit(proc.pid, timeout_s=0.2) is False
    finally:
        _force_cleanup(control, [proc.pid])


def test_kill_tree_on_a_dead_pid_still_reports_what_it_signalled(mods):
    _, control = mods
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    assert control.kill_tree(proc.pid) == [proc.pid]


def test_posix_descendant_walk_is_a_no_op_where_ps_is_absent(mods):
    """`ps --ppid` is the POSIX half; on Windows the lookup must not raise."""
    _, control = mods
    assert control._descendant_pids_windows_free(os.getpid()) == []
