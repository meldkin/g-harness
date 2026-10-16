#!/usr/bin/env python3
"""Tests for .github/scripts/eval_harness.py — the harness self-evaluator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "eval_harness.py"

_AGENTS_OK = "\n".join(
    [
        "## Behavior Rules",
        "## Security Rules",
        "## Known Constraints",
        "## Not Allowed",
        "## Escalation",
        "## Verification Gates",
        "## Git Commit Convention",
    ]
)


def _load():
    spec = importlib.util.spec_from_file_location("eval_harness_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _artifacts_project(tmp: Path) -> Path:
    """Build just enough of a project for the `artifacts` suite to pass."""
    (tmp / "AGENTS.md").write_text(_AGENTS_OK, encoding="utf-8")
    (tmp / ".github" / "scripts").mkdir(parents=True)
    (tmp / ".github" / "scripts" / "checklist.py").write_text("", encoding="utf-8")
    (tmp / ".kilo" / "instruction").mkdir(parents=True)
    (tmp / ".kilo" / "instruction" / "harness-checklist.md").write_text(
        "", encoding="utf-8"
    )
    (tmp / ".kilo" / "templates").mkdir(parents=True)
    (tmp / ".kilo" / "templates" / "IMPLEMENT.md").write_text("", encoding="utf-8")
    (tmp / ".kilo" / "command").mkdir(parents=True)
    for cmd in ("plan", "verify", "debug", "test", "brainstorm", "decide"):
        (tmp / ".kilo" / "command" / f"{cmd}.md").write_text("", encoding="utf-8")
    return tmp


# ── result bookkeeping ───────────────────────────────────────────────────────


def test_result_recording_and_verbose(capsys):
    mod = _load()
    runner = mod.EvalRunner(Path("."), verbose=True)
    runner.ok("a", "security")
    runner.fail("b", "security", "because")
    runner.assert_true(True, "c", "hooks")
    runner.assert_true(False, "d", "hooks", "nope")
    runner.assert_file(Path(__file__), "e", "artifacts")
    runner.assert_file(Path("missing-xyz"), "f")
    names = [r.name for r in runner.results]
    assert names == ["a", "b", "c", "d", "e", "f"]
    assert sum(1 for r in runner.results if r.passed) == 3
    out = capsys.readouterr().out
    assert "PASS" in out and "\x1b[0m a" in out
    assert "FAIL" in out and "b: because" in out


def test_run_node_check_outcomes(monkeypatch, tmp_path):
    mod = _load()
    runner = mod.EvalRunner(tmp_path)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stderr=""),
    )
    assert runner.run_node_check(tmp_path / "x.js") == (True, "")
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stderr=" SyntaxError"),
    )
    assert runner.run_node_check(tmp_path / "x.js") == (False, "SyntaxError")

    def no_node(*_a, **_k):
        raise FileNotFoundError

    monkeypatch.setattr(mod.subprocess, "run", no_node)
    assert runner.run_node_check(tmp_path / "x.js") == (False, "node not found")

    def slow(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="node", timeout=10)

    monkeypatch.setattr(mod.subprocess, "run", slow)
    assert runner.run_node_check(tmp_path / "x.js") == (False, "timeout")


# ── security suite ───────────────────────────────────────────────────────────


def test_eval_security_patterns_passes_on_a_configured_project(tmp_path):
    mod = _load()
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "security_scan.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    (tmp_path / "kilo.jsonc").write_text(
        '{"x": "rm -rf /*", "y": "DROP TABLE", "z": "git push --force"}',
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text(
        "security_scan.py\nNever hardcode credentials\n", encoding="utf-8"
    )
    runner = mod.EvalRunner(tmp_path)
    runner.eval_security_patterns()
    assert all(r.passed for r in runner.results), [
        r for r in runner.results if not r.passed
    ]


def test_eval_security_patterns_flags_missing_patterns(tmp_path):
    mod = _load()
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "security_scan.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    (tmp_path / "kilo.jsonc").write_text("{}", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("nothing here", encoding="utf-8")
    runner = mod.EvalRunner(tmp_path)
    runner.eval_security_patterns()
    assert any(not r.passed for r in runner.results)


# ── hooks suite ──────────────────────────────────────────────────────────────


def test_eval_hooks_integrity(tmp_path, monkeypatch):
    mod = _load()
    hooks = tmp_path / ".kilo" / "hooks"
    (hooks / "pre-tool-use").mkdir(parents=True)
    (hooks / "post-tool-use").mkdir(parents=True)
    (hooks / "session").mkdir(parents=True)
    (hooks / "hooks.json").write_text(
        json.dumps(
            {"hooks": {"a": [1], "b": [2], "c": [3], "d": [4], "e": [5], "f": [6]}}
        ),
        encoding="utf-8",
    )
    for rel in (
        "pre-tool-use/gate-guard.js",
        "pre-tool-use/secret-scan.js",
        "pre-tool-use/config-protection.js",
        "pre-tool-use/governance-capture.js",
        "post-tool-use/quality-gate.js",
        "post-tool-use/console-log-check.js",
        "post-tool-use/context-monitor.js",
        "post-tool-use/edit-accumulator.js",
        "session/session-start.js",
        "session/session-end.js",
    ):
        (hooks / rel).write_text("", encoding="utf-8")
    runner = mod.EvalRunner(tmp_path)
    monkeypatch.setattr(runner, "run_node_check", lambda _s: (True, ""))
    runner.eval_hooks_integrity()
    assert all(r.passed for r in runner.results), [
        r for r in runner.results if not r.passed
    ]


def test_eval_hooks_integrity_bad_json(tmp_path, monkeypatch):
    mod = _load()
    hooks = tmp_path / ".kilo" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "hooks.json").write_text("{ not json", encoding="utf-8")
    runner = mod.EvalRunner(tmp_path)
    monkeypatch.setattr(runner, "run_node_check", lambda _s: (True, ""))
    runner.eval_hooks_integrity()
    assert any(not r.passed for r in runner.results)


# ── artifacts / context suites ───────────────────────────────────────────────


def test_eval_artifacts_passes(tmp_path):
    mod = _load()
    runner = mod.EvalRunner(_artifacts_project(tmp_path))
    runner.eval_artifacts()
    assert all(r.passed for r in runner.results), [
        r for r in runner.results if not r.passed
    ]


def test_eval_artifacts_flags_template_marker(tmp_path):
    mod = _load()
    project = _artifacts_project(tmp_path)
    (project / "AGENTS.md").write_text(
        _AGENTS_OK + "\n<!-- One paragraph: x -->\n", encoding="utf-8"
    )
    runner = mod.EvalRunner(project)
    runner.eval_artifacts()
    assert any(
        "unfilled template markers" in r.name and not r.passed for r in runner.results
    )


def test_eval_context_management(tmp_path):
    mod = _load()
    (tmp_path / ".kilo" / "hooks" / "post-tool-use").mkdir(parents=True)
    (tmp_path / ".kilo" / "hooks" / "session").mkdir(parents=True)
    (tmp_path / ".kilo" / "state").mkdir(parents=True)
    (tmp_path / ".kilo" / "hooks" / "post-tool-use" / "context-monitor.js").write_text(
        "OUTPUT_TRIM_LINES checkToolOutputSize NEVER modifies TOOL_CALL_WARN_1 "
        "TOOL_CALL_WARN_2 TOKEN_LOG_FILE HIGH_OUTPUT_TOOLS estimateTokens\n",
        encoding="utf-8",
    )
    (tmp_path / ".kilo" / "hooks" / "session" / "session-end.js").write_text(
        "Session Summary estimatedCostUSD formatDuration\n", encoding="utf-8"
    )
    runner = mod.EvalRunner(tmp_path)
    runner.eval_context_management()
    assert all(r.passed for r in runner.results), [
        r for r in runner.results if not r.passed
    ]


def test_eval_context_management_flags_legacy_functions(tmp_path):
    mod = _load()
    hooks = tmp_path / ".kilo" / "hooks" / "post-tool-use"
    hooks.mkdir(parents=True)
    (hooks / "context-monitor.js").write_text(
        "buildTrimmedResponse\n", encoding="utf-8"
    )
    runner = mod.EvalRunner(tmp_path)
    runner.eval_context_management()
    assert any(not r.passed for r in runner.results)


# ── summary / main ───────────────────────────────────────────────────────────


def test_print_summary_all_pass(capsys):
    mod = _load()
    runner = mod.EvalRunner(Path("."))
    runner.ok("a", "security")
    runner.ok("b", "hooks")
    assert runner.print_summary() is True
    assert "All evals passed" in capsys.readouterr().out


def test_print_summary_with_failures_verbose(capsys):
    mod = _load()
    runner = mod.EvalRunner(Path("."), verbose=True)
    runner.ok("a", "security")
    runner.fail("b", "security", "broken")
    assert runner.print_summary() is False
    out = capsys.readouterr().out
    assert "FAILED" in out and "b: broken" in out


def test_main_missing_project(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["eval_harness.py", "does-not-exist-xyz"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert "does not exist" in capsys.readouterr().out


def test_main_artifacts_suite_on_a_good_project(monkeypatch, tmp_path):
    mod = _load()
    _artifacts_project(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["eval_harness.py", str(tmp_path), "--suite", "artifacts"]
    )
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0


def test_main_failing_suite_exits_one(monkeypatch, tmp_path):
    mod = _load()
    (tmp_path / ".kilo").mkdir()  # context suite will miss the state dir
    monkeypatch.setattr(
        sys, "argv", ["eval_harness.py", str(tmp_path), "--suite", "context"]
    )
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
