#!/usr/bin/env python3
"""Tests for tools/gui_server.py — the local JEV worker console."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "gui_server.py"


def _load():
    spec = importlib.util.spec_from_file_location("gui_server_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── discovery ────────────────────────────────────────────────────────────────


def test_env_key_names_returns_names_not_values(tmp_path):
    mod = _load()
    p = tmp_path / ".env"
    p.write_text("# comment\nA_KEY=super-secret\n\nB=2\nA_KEY=dup\n", encoding="utf-8")
    names = mod.env_key_names(p)
    assert names == ["A_KEY", "B"]
    assert all("secret" not in n for n in names)


def test_env_key_names_missing_file(tmp_path):
    assert _load().env_key_names(tmp_path / "nope") == []


def test_providers_reads_catalog(tmp_path):
    mod = _load()
    p = tmp_path / "opencode.json"
    p.write_text(
        json.dumps(
            {"providers": {"x": {"models": {"m1": {}, "m2": {}}}, "y": {"models": {}}}}
        ),
        encoding="utf-8",
    )
    assert mod.providers(p) == {"x": ["m1", "m2"], "y": []}


def test_providers_bad_json_is_empty(tmp_path):
    mod = _load()
    p = tmp_path / "opencode.json"
    p.write_text("{ not json", encoding="utf-8")
    assert mod.providers(p) == {}


def test_known_models_builds_flat_refs():
    mod = _load()
    assert mod.known_models({"b": ["k2"], "a": ["k1"]}) == [
        {"provider": "a", "key": "k1", "ref": "a/k1"},
        {"provider": "b", "key": "k2", "ref": "b/k2"},
    ]


def test_workers_ready_requires_cli_and_wrapper(tmp_path, monkeypatch):
    mod = _load()
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "antigravity_delegate.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        mod.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "agy" else None
    )
    by_id = {w["id"]: w for w in mod.workers(tmp_path)}
    assert by_id["gemini"]["ready"] is True
    assert by_id["opencode"]["ready"] is False  # CLI present? no -> not ready
    assert by_id["codex"]["ready"] is False  # note set (wrapper pending)
    assert by_id["codex"]["note"]


# ── argv builder / validation (the security-relevant part) ───────────────────


def test_build_argv_gemini_with_tools():
    mod = _load()
    argv = mod.build_argv(
        "gemini", "do x", "gemini-3.8-flash-medium", {"allow_tools": True}
    )
    assert argv == [
        sys.executable,
        "tools/antigravity_delegate.py",
        "do x",
        "--model",
        "gemini-3.8-flash-medium",
        "--allow-tools",
    ]


def test_build_argv_opencode_free():
    mod = _load()
    assert mod.build_argv("opencode", "b", None, {"free": True}) == [
        sys.executable,
        "tools/opencode_delegate.py",
        "b",
        "--free",
    ]


def test_build_argv_kilo_and_dsh():
    mod = _load()
    assert mod.build_argv("kilo", "b", "m", {}) == [
        sys.executable,
        "tools/kilo_cli_delegate.py",
        "b",
        "--model",
        "m",
    ]
    assert mod.build_argv("dsh", "b", None, {}) == [
        sys.executable,
        "tools/dsh_delegate.py",
        "b",
    ]


def test_build_argv_rejects_pending_worker():
    mod = _load()
    with pytest.raises(ValueError):
        mod.build_argv("codex", "b", None, {})


def test_validate_run_accepts_and_rejects():
    mod = _load()
    mod.validate_run("opencode", "x", None, set())
    mod.validate_run("gemini", "x", "prov/key", {"prov/key"})
    for args in (
        ("codex", "x", None, set()),
        ("opencode", "   ", None, set()),
        ("opencode", "x" * 25_000, None, set()),
        ("gemini", "x", "prov/nope", {"prov/key"}),
    ):
        with pytest.raises(ValueError):
            mod.validate_run(*args)


# ── HTTP surface ─────────────────────────────────────────────────────────────


@pytest.fixture()
def server():
    mod = _load()
    httpd = mod.build_server("127.0.0.1", 0, "tok123", 30)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield mod, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def _call(port, path, *, token=None, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-Token": token} if token else {}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:  # noqa: S310 — fixed 127.0.0.1 URL
            return res.status, res.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def test_index_is_public_and_carries_the_token(server):
    _, port = server
    status, body = _call(port, "/")
    assert status == 200
    assert "JEV Worker Console" in body
    assert "tok123" in body  # injected so the page can call the API


def test_state_requires_token(server):
    _, port = server
    assert _call(port, "/api/state")[0] == 403
    status, body = _call(port, "/api/state", token="tok123")  # noqa: S106 — test fixture
    assert status == 200
    assert "workers" in json.loads(body)


def test_run_rejects_non_runnable_worker(server):
    _, port = server
    status, body = _call(
        port,
        "/api/run",
        token="tok123",
        method="POST",  # noqa: S106 — test fixture
        payload={"worker": "codex", "brief": "x"},
    )
    assert status == 400
    assert "not runnable" in body


def test_run_ok_with_mocked_runner(server, monkeypatch):
    mod, port = server
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda w, b, m, f, t: {
            "argv": ["x"],
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
        },
    )
    status, body = _call(
        port,
        "/api/run",
        token="tok123",
        method="POST",  # noqa: S106 — test fixture
        payload={"worker": "opencode", "brief": "do x"},
    )
    assert status == 200
    assert json.loads(body)["stdout"] == "ok"
