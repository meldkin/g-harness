#!/usr/bin/env python3
"""Tests for tools/win_sandbox.py — Windows ACL restricted-token confinement.

The pure layer (path identity, argv parsing, SID derivation, quoting) runs on
every platform. The confinement layer is exercised for real on Windows: the
availability probe, SID comparison, ACL grant/revoke idempotency, a confined
spawn, and the runner boundary (writes inside allowed, outside denied).
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "win_sandbox.py"
# The runner's own failure exit: the child never ran, so a denial that carries
# this code proves nothing about enforcement.
RUNNER_FAILURE_EXIT = 127

WIN_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows ACL restricted tokens are Windows-only"
)


def _load():
    spec = importlib.util.spec_from_file_location("win_sandbox_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@contextmanager
def _normal_acl_dir():
    """A temp root with a normal inheritable ACL.

    PyTest's numbered basetemp (``.pytest_temp``) carries a PROTECTED DACL that
    names only Owner Rights/System/Administrators, and ``tempfile.mkdtemp``
    applies the same protected DACL. Under a WRITE_RESTRICTED token the owner
    then has no explicit write ACE on any child, so confinement fails there for
    a reason unrelated to this module. A plain ``mkdir`` under ``%TEMP%``
    inherits the usual caller-owned ACL a real workspace has.
    """
    root = (
        Path(tempfile.gettempdir())
        / f"win-sandbox-test-{os.getpid()}-{uuid.uuid4().hex}"
    )
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _has_capability_ace(path: Path) -> bool:
    """Read the directory's DACL and ask whether its capability ACE sits on it."""
    mod = _load()
    k32, adv = mod._api()
    sid = mod._parse_sid(adv, mod.workspace_write_sid(str(path)))
    try:
        old_acl, descriptor = mod._read_current_dacl(k32, adv, str(path))
        try:
            return bool(old_acl) and mod._has_exact_grant(old_acl, sid)
        finally:
            if descriptor:
                k32.LocalFree(ctypes.c_void_p(descriptor))
    finally:
        k32.LocalFree(ctypes.c_void_p(sid))


# ── pure: path identity and boundaries ───────────────────────────────────────


def test_canonical_path_is_absolute(tmp_path):
    mod = _load()
    assert Path(mod.canonical_path(str(tmp_path))).is_absolute()


def test_contains_directory_identity_child_and_sibling(tmp_path):
    mod = _load()
    root = tmp_path / "root"
    child = root / "child"
    sibling = tmp_path / "sibling"
    child.mkdir(parents=True)
    sibling.mkdir()
    assert mod.contains_directory(str(root), str(root)) is True
    assert mod.contains_directory(str(root), str(child)) is True
    assert mod.contains_directory(str(child), str(root)) is False
    assert mod.contains_directory(str(root), str(sibling)) is False


def test_workspace_write_sid_is_deterministic_and_distinct(tmp_path):
    mod = _load()
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    assert mod.workspace_write_sid(a) == mod.workspace_write_sid(a)
    assert mod.workspace_write_sid(a) != mod.workspace_write_sid(b)
    assert mod.workspace_write_sid(a).startswith("S-1-4-")
    assert not mod.workspace_write_sid(a).endswith("-1")


def test_temp_write_sid_is_domain_separated(tmp_path):
    mod = _load()
    root = str(tmp_path)
    assert mod.temp_write_sid(root) != mod.workspace_write_sid(root)
    assert mod.temp_write_sid(root).endswith("-1")
    assert (
        mod.temp_write_sid(root).count("-")
        == mod.workspace_write_sid(root).count("-") + 1
    )


def test_assert_temp_root_outside_workspace(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    inside = ws / "tmp"
    inside.mkdir(parents=True)
    with pytest.raises(ValueError):
        mod.assert_temp_root_outside_workspace(str(ws), str(inside))
    mod.assert_temp_root_outside_workspace(str(ws), str(tmp_path / "outside"))


def test_assert_private_temp_disjoint(tmp_path):
    mod = _load()
    writable = tmp_path / "writable"
    nested = writable / "temp"
    nested.mkdir(parents=True)
    with pytest.raises(ValueError):
        mod.assert_private_temp_disjoint([str(writable)], str(nested))
    with pytest.raises(ValueError):
        mod.assert_private_temp_disjoint([str(nested)], str(writable))
    assert (
        mod.assert_private_temp_disjoint([str(writable)], str(tmp_path / "other"))
        is None
    )


# ── pure: command-line quoting ───────────────────────────────────────────────


def test_windows_command_line_quoting():
    mod = _load()
    assert mod.windows_command_line([]) == ""
    assert mod.windows_command_line(["plain"]) == "plain"
    assert mod.windows_command_line([""]) == '""'
    assert mod.windows_command_line(["a b"]) == '"a b"'
    assert mod.windows_command_line(["a b", 'c"d']) == '"a b" "c\\"d"'


# ── pure: runner argv contract ───────────────────────────────────────────────


def test_parse_runner_argv_accepts_the_contract():
    mod = _load()
    parsed = mod.parse_runner_argv(
        [
            "--workspace",
            "w",
            "--temp",
            "t",
            "--mode",
            "read-only",
            "--",
            "cmd",
            "/c",
            "x",
        ]
    )
    assert parsed.workspace == "w"
    assert parsed.temp == "t"
    assert parsed.mode == "read-only"
    assert parsed.argv == ["cmd", "/c", "x"]
    assert parsed.seam_managed is False
    assert parsed.also_write == []


def test_parse_runner_argv_collects_every_also_write():
    mod = _load()
    parsed = mod.parse_runner_argv(
        [
            "--workspace",
            "w",
            "--temp",
            "t",
            "--mode",
            "workspace-write",
            "--also-write",
            "a",
            "--also-write",
            "b",
            "--",
            "cmd",
        ]
    )
    assert parsed.also_write == ["a", "b"]


def test_parse_runner_argv_rejects_bad_input():
    mod = _load()
    cases = [
        ["--workspace", "w", "--temp", "t", "--mode", "nope", "--", "x"],
        ["--workspace", "w", "--temp", "t", "--", "x"],
        ["--workspace", "w", "--mode", "read-only", "--", "x"],
        ["--temp", "t", "--mode", "read-only", "--", "x"],
        ["--workspace", "w", "--temp", "t", "--mode", "read-only"],
        ["--bogus", "w", "--temp", "t", "--mode", "read-only", "--", "x"],
        ["--workspace", "--temp", "t", "--mode", "read-only", "--", "x"],
    ]
    for raw in cases:
        with pytest.raises(ValueError):
            mod.parse_runner_argv(raw)


# ── pure: sandbox construction validation ────────────────────────────────────


def test_win_sandbox_rejects_a_missing_workspace(tmp_path):
    mod = _load()
    with pytest.raises(ValueError):
        mod.WinSandbox(mode="read-only", workspace_root=str(tmp_path / "absent"))


def test_win_sandbox_workspace_write_requires_temp(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(ValueError):
        mod.WinSandbox(mode="workspace-write", workspace_root=str(ws))


def test_win_sandbox_read_only_rejects_temp(tmp_path):
    mod = _load()
    ws, tmp = tmp_path / "ws", tmp_path / "tmp"
    ws.mkdir()
    tmp.mkdir()
    with pytest.raises(ValueError):
        mod.WinSandbox(mode="read-only", workspace_root=str(ws), temp_dir=str(tmp))


def test_win_sandbox_rejects_temp_inside_workspace(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    inside = ws / "tmp"
    inside.mkdir(parents=True)
    with pytest.raises(ValueError):
        mod.WinSandbox(
            mode="workspace-write", workspace_root=str(ws), temp_dir=str(inside)
        )


def test_also_write_needs_workspace_write(tmp_path):
    mod = _load()
    ws, extra = tmp_path / "ws", tmp_path / "extra"
    ws.mkdir()
    extra.mkdir()
    with pytest.raises(ValueError):
        mod.WinSandbox(
            mode="read-only", workspace_root=str(ws), also_write=[str(extra)]
        )


def test_also_write_must_be_a_directory(tmp_path):
    mod = _load()
    ws, tmp = tmp_path / "ws", tmp_path / "tmp"
    ws.mkdir()
    tmp.mkdir()
    with pytest.raises(ValueError):
        mod.WinSandbox(
            mode="workspace-write",
            workspace_root=str(ws),
            temp_dir=str(tmp),
            also_write=[str(tmp_path / "absent")],
        )


def test_spawn_before_init_and_dispose_without_init(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    sandbox = mod.WinSandbox(mode="read-only", workspace_root=str(ws))
    with pytest.raises(RuntimeError):
        sandbox.spawn(["cmd", "/c", "echo"])
    sandbox.dispose()  # never initialized: a no-op, never a crash


# ── pure: self-test and no-arg main ──────────────────────────────────────────


def test_main_self_test_exits_zero(capsys):
    mod = _load()
    assert mod.main(["--self-test"]) == 0
    assert "self-test passed" in capsys.readouterr().out


def test_revert_without_a_scope_is_a_usage_error(capsys):
    mod = _load()
    assert mod.main(["revert"]) == 1
    assert "pass --workspace, --temp and/or --also-write" in capsys.readouterr().err


# ── Windows: availability, SID machinery, ACLs, confinement ──────────────────


@WIN_ONLY
def test_probe_reports_this_host_supports_restricted_tokens(capsys):
    mod = _load()
    result = mod.probe()
    assert result["available"] is True
    assert result["enforcement"] == "partial"
    assert mod.main(["probe"]) == 0
    assert json.loads(capsys.readouterr().out)["available"] is True


@WIN_ONLY
def test_local_alloc_is_freed():
    mod = _load()
    k32, _adv = mod._api()
    memory = mod._local_alloc(k32, 16)
    assert memory
    k32.LocalFree(ctypes.c_void_p(memory))


@WIN_ONLY
def test_sid_equals_matches_and_differs():
    mod = _load()
    k32, adv = mod._api()
    first = mod._parse_sid(adv, "S-1-5-18")
    same = mod._parse_sid(adv, "S-1-5-18")
    other = mod._parse_sid(adv, "S-1-5-19")
    try:
        assert mod._sid_equals(first, same) is True
        assert mod._sid_equals(first, other) is False
    finally:
        for sid in (first, same, other):
            k32.LocalFree(ctypes.c_void_p(sid))


@WIN_ONLY
def test_create_restricted_token_requires_write_sids():
    mod = _load()
    k32, adv = mod._api()
    with pytest.raises(mod.RunnerFailure):
        mod._create_restricted_token(k32, adv, 1, 2, 3, [], "workspace-write")


@WIN_ONLY
def test_grant_write_is_idempotent_and_detected(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    k32, adv = mod._api()
    sid = mod._parse_sid(adv, mod.workspace_write_sid(str(ws)))
    try:
        mod.grant_write(str(ws), sid)
        old_acl, descriptor = mod._read_current_dacl(k32, adv, str(ws))
        try:
            assert mod._has_exact_grant(old_acl, sid) is True
        finally:
            k32.LocalFree(ctypes.c_void_p(descriptor))
        mod.grant_write(str(ws), sid)  # second call takes the exact-ACE skip
        assert mod.revoke_write(str(ws), sid) is True
    finally:
        k32.LocalFree(ctypes.c_void_p(sid))


@WIN_ONLY
def test_win_sandbox_read_only_init_spawn_dispose(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    sandbox = mod.WinSandbox(mode="read-only", workspace_root=str(ws))
    sandbox.init()
    try:
        with pytest.raises(RuntimeError):
            sandbox.init()
        result = sandbox.spawn(["cmd", "/c", "echo", "hi"])
        assert result.exit_code == 0
        assert result.pid > 0
    finally:
        sandbox.dispose()
    with pytest.raises(RuntimeError):
        sandbox.spawn(["cmd", "/c", "echo"])


@WIN_ONLY
def test_runner_read_only_runs_the_child(tmp_path):
    ws, tmp = tmp_path / "ws", tmp_path / "tmp"
    ws.mkdir()
    tmp.mkdir()
    proc = _run_cli(
        "run",
        "--workspace",
        str(ws),
        "--temp",
        str(tmp),
        "--mode",
        "read-only",
        "--",
        "cmd",
        "/c",
        "echo CONFINED_OK",
    )
    assert proc.returncode == 0
    assert "CONFINED_OK" in proc.stdout


@WIN_ONLY
def test_runner_read_only_denies_a_write_inside_the_workspace():
    """Read-only's promise is deny-everywhere, measured against a writable control."""
    with _normal_acl_dir() as root:
        ws, tmp = root / "ws", root / "tmp"
        ws.mkdir()
        tmp.mkdir()

        allowed = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            "echo x> control.txt",
        )
        assert allowed.returncode == 0
        assert (ws / "control.txt").exists()

        denied = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "read-only",
            "--",
            "cmd",
            "/c",
            "echo x> read-only.txt",
        )
        # The child must have run and been denied. ``!= 0`` alone would also
        # accept a runner crash (exit 127), which proves no enforcement at all.
        assert denied.returncode not in (0, RUNNER_FAILURE_EXIT)
        assert "harness-acl-run:" not in denied.stderr
        assert not (ws / "read-only.txt").exists()


@WIN_ONLY
def test_runner_workspace_write_allows_inside_denies_outside():
    with _normal_acl_dir() as root:
        ws, tmp = root / "ws", root / "tmp"
        ws.mkdir()
        tmp.mkdir()
        outside = root / "outside.txt"

        inside = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            "echo x> inside.txt",
        )
        assert inside.returncode == 0
        assert (ws / "inside.txt").exists()

        denied = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            f"echo x> {outside}",
        )
        assert denied.returncode != 0
        assert not outside.exists()


@WIN_ONLY
def test_runner_reports_a_missing_workspace(tmp_path):
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    proc = _run_cli(
        "run",
        "--workspace",
        str(tmp_path / "absent"),
        "--temp",
        str(tmp),
        "--mode",
        "read-only",
        "--",
        "cmd",
        "/c",
        "echo",
    )
    assert proc.returncode == 127
    assert proc.stderr.startswith("harness-acl-run:")


# ── Windows: revert (the way back from the standing workspace ACE) ───────────


@WIN_ONLY
def test_revert_drops_the_ace_a_run_leaves_standing():
    with _normal_acl_dir() as root:
        ws, tmp = root / "ws", root / "tmp"
        ws.mkdir()
        tmp.mkdir()
        run = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            "echo x> inside.txt",
        )
        assert run.returncode == 0
        assert _has_capability_ace(ws) is True

        first = _run_cli("revert", "--workspace", str(ws))
        assert first.returncode == 0
        assert json.loads(first.stdout)["workspace"]["removed"] is True
        assert _has_capability_ace(ws) is False

        # Nothing left to remove is a success, not an error: revert is idempotent.
        second = _run_cli("revert", "--workspace", str(ws))
        assert second.returncode == 0
        assert json.loads(second.stdout)["workspace"]["removed"] is False


@WIN_ONLY
def test_revert_takes_the_temp_ace_off():
    with _normal_acl_dir() as root:
        tmp = root / "tmp"
        tmp.mkdir()
        mod = _load()
        k32, adv = mod._api()
        sid = mod._parse_sid(adv, mod.temp_write_sid(str(tmp)))
        try:
            mod.grant_write(str(tmp), sid)
        finally:
            k32.LocalFree(ctypes.c_void_p(sid))

        first = _run_cli("revert", "--temp", str(tmp))
        assert first.returncode == 0
        assert json.loads(first.stdout)["temp"]["removed"] is True
        second = _run_cli("revert", "--temp", str(tmp))
        assert json.loads(second.stdout)["temp"]["removed"] is False


@WIN_ONLY
def test_revert_reports_a_missing_directory(tmp_path):
    proc = _run_cli("revert", "--workspace", str(tmp_path / "absent"))
    assert proc.returncode == 1
    assert proc.stderr.startswith("win_sandbox revert:")


@WIN_ONLY
def test_also_write_opens_one_extra_root_then_revokes_it():
    """A worker's state dir needs a grant; unlike the workspace, it is temporary."""
    with _normal_acl_dir() as root:
        ws, tmp, state = root / "ws", root / "tmp", root / "state"
        for path in (ws, tmp, state):
            path.mkdir()
        target = state / "ok.txt"

        denied = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            f"echo x> {target}",
        )
        assert denied.returncode != 0
        assert not target.exists()

        allowed = _run_cli(
            "run",
            "--workspace",
            str(ws),
            "--temp",
            str(tmp),
            "--also-write",
            str(state),
            "--mode",
            "workspace-write",
            "--",
            "cmd",
            "/c",
            f"echo x> {target}",
        )
        assert allowed.returncode == 0
        assert target.exists()

        # Disposed with the run, so the caller's own directory gets its DACL back.
        assert _has_capability_ace(state) is False


# The CLI tests above drive the real seam, but they run in a child process, so
# coverage cannot see the functions they exercise. These call the same ones
# in-process — same assertions, visible to the ratchet.


@WIN_ONLY
def test_revoke_grant_reports_presence_then_absence(tmp_path):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    sid_string = mod.workspace_write_sid(str(ws))
    k32, adv = mod._api()
    sid = mod._parse_sid(adv, sid_string)
    try:
        mod.grant_write(str(ws), sid)
    finally:
        k32.LocalFree(ctypes.c_void_p(sid))

    assert mod.revoke_grant(str(ws), sid_string) is True
    assert mod.revoke_grant(str(ws), sid_string) is False
    assert _has_capability_ace(ws) is False


@WIN_ONLY
def test_revert_in_process_reports_an_absent_grant(tmp_path, capsys):
    mod = _load()
    ws = tmp_path / "ws"
    ws.mkdir()
    assert mod._revert(str(ws), None) == 0
    assert json.loads(capsys.readouterr().out)["workspace"]["removed"] is False

    # A missing directory is a refused scope, not a traceback.
    assert mod._revert(str(tmp_path / "absent"), None) == 1
    assert capsys.readouterr().err.startswith("win_sandbox revert:")


@WIN_ONLY
def test_sandbox_grants_and_revokes_an_extra_root_in_process(tmp_path):
    """The extra-root grant lifecycle, called directly so coverage can see it."""
    mod = _load()
    ws, tmp, state = tmp_path / "ws", tmp_path / "tmp", tmp_path / "state"
    for path in (ws, tmp, state):
        path.mkdir()
    sandbox = mod.WinSandbox(
        mode="workspace-write",
        workspace_root=str(ws),
        temp_dir=str(tmp),
        also_write=[str(state)],
    )
    sandbox.init()
    try:
        assert _has_capability_ace(state) is True
    finally:
        sandbox.dispose()
    assert _has_capability_ace(state) is False


@WIN_ONLY
def test_revert_in_process_reports_an_extra_root(tmp_path, capsys):
    mod = _load()
    state = tmp_path / "state"
    state.mkdir()
    sid_string = mod.workspace_write_sid(str(state))
    k32, adv = mod._api()
    sid = mod._parse_sid(adv, sid_string)
    try:
        mod.grant_write(str(state), sid)
    finally:
        k32.LocalFree(ctypes.c_void_p(sid))

    assert mod._revert(None, None, [str(state)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report[str(state)]["removed"] is True
