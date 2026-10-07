#!/usr/bin/env python3
"""codex_delegate.py — run a Codex (ChatGPT) worker through the harness.

Why this exists: Codex is the one fleet member with **no project hook API**, so
it cannot be fenced by `.claude/hooks/guard.py` or the Kilo `gate-guard.js` the
way the other engines are. This wrapper supplies the fence instead:

  1. a **sandbox flag** — `read-only` by default, `workspace-write` only with
     `--allow-write`; `danger-full-access` is never emitted;
  2. a **guardrail brief** written to a file (NOT passed inline: on Windows the
     npm `.ps1` shim mangles multi-line arguments, truncating them to line 1),
     referenced from a single-line prompt;
  3. a **post-run change summary** (`git status` + `git diff --stat`) captured
     into the result, because a Codex run is only trustworthy once the operator
     inspects what it actually wrote.

Codex is launched through `codex-env.ps1` (loads `.env` → `OPENAI_API_KEY`,
injects the base URL). That launcher is an unsigned PowerShell script, so it is
invoked with a process-scoped `-ExecutionPolicy Bypass` — it does not change the
machine policy.

The result is a `| Claim | Command run | Output |`-style record: the orchestrator
must still re-run the commands itself; worker self-assessment is not evidence.

Usage:
    python tools/codex_delegate.py "add a test for foo()" --dry-run
    python tools/codex_delegate.py "add a test for foo()"
    python tools/codex_delegate.py "refactor x" --allow-write --model gpt-6.1-sol
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # noqa: S404 — fixed argv; the browser/task cannot inject
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "codex-env.ps1"
USAGE_LOG = ROOT / ".solocode" / "codex-delegate-usage.jsonl"
DEFAULT_TIMEOUT = 900
DEFAULT_MODEL = "gpt-6.1-sol"

GUARDRAIL = """\
STRICT OPERATING CONSTRAINTS (follow exactly):
1. Do NOT run destructive commands (rm -rf, git push --force, DROP/DELETE,
   force-remove, format, shutdown, anything that deletes more than a build dir).
2. Make the SMALLEST change that satisfies the task; do not refactor unrelated
   code and do not add dependencies unless the task says to.
3. Match the surrounding code style exactly.
4. End with a one-line self-check: what you changed, and which commands you ran.

You are a worker: the orchestrator will re-run your commands and inspect the
diff. Do not claim a result you did not verify.
"""


def _find_powershell() -> str | None:
    """Resolve powershell.exe so the argv[0] is absolute (no partial path)."""
    return shutil.which("powershell") or shutil.which("pwsh")


def build_plan(
    task: str,
    *,
    model: str | None = None,
    allow_write: bool = False,
    brief_file: Path,
    out_file: Path,
    root: Path = ROOT,
    powershell: str = "powershell",
) -> dict[str, object]:
    """Build the launch plan. Pure — this is the security-relevant part."""
    sandbox = "workspace-write" if allow_write else "read-only"
    argv = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "codex-env.ps1"),
        "exec",
        "--ephemeral",
        "-s",
        sandbox,
        "-C",
        str(root),
        "-o",
        str(out_file),
    ]
    if model:
        argv += ["-m", model]
    argv.append(
        f"Read the file {brief_file} and carry out the task it contains exactly. "
        "It is your complete brief."
    )
    return {"argv": argv, "brief": GUARDRAIL + "\n" + task, "sandbox": sandbox}


def change_summary(root: Path = ROOT) -> dict[str, str]:
    """Post-run view of what changed, so the operator can inspect it."""

    def _git(*args: str) -> str:
        try:
            proc = subprocess.run(  # noqa: S603, S607 — fixed argv (git + constant flags)
                ["git", "-C", str(root), *args],  # noqa: S607 — fixed argv
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return proc.stdout.strip()

    return {"status": _git("status", "--porcelain"), "diffstat": _git("diff", "--stat")}


def run_plan(argv: list[str], out_file: Path, timeout_s: int) -> tuple[int, str]:
    """Execute the plan and read Codex's final message from `-o`."""
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv; brief is data, not a command
            argv, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        return 3, f"timeout after {timeout_s}s"
    except OSError as exc:
        return 4, f"failed to launch: {exc}"
    text = ""
    if out_file.is_file():
        text = out_file.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return proc.returncode, (text or proc.stderr or proc.stdout)
    return (0 if text.strip() else 2), text


def log_usage(model: str | None, sandbox: str, elapsed: float, code: int) -> None:
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model or DEFAULT_MODEL,
            "sandbox": sandbox,
            "elapsed_s": round(elapsed, 2),
            "exit": code,
        }
        with USAGE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # usage logging must never break a run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex (ChatGPT) worker delegate")
    parser.add_argument("task", help="self-contained task brief")
    parser.add_argument(
        "--model", default=None, help=f"Codex model (default {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="use the workspace-write sandbox (default: read-only)",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the plan and exit"
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print(
            "ERROR: codex-env.ps1 is Windows-only; no POSIX launcher is wired.",
            file=sys.stderr,
        )
        return 1
    if not LAUNCHER.is_file():
        print(f"ERROR: {LAUNCHER} not found.", file=sys.stderr)
        return 1
    powershell = _find_powershell()
    if not powershell:
        print("ERROR: powershell/pwsh not found on PATH.", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="codex-delegate-"))
    brief_file = tmp / "brief.md"
    out_file = tmp / "last-message.md"
    plan = build_plan(
        args.task,
        model=args.model,
        allow_write=args.allow_write,
        brief_file=brief_file,
        out_file=out_file,
        powershell=powershell,
    )
    brief_file.write_text(str(plan["brief"]), encoding="utf-8")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "argv": plan["argv"],
                    "sandbox": plan["sandbox"],
                    "brief": str(brief_file),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    start = time.monotonic()
    code, output = run_plan(list(plan["argv"]), out_file, args.timeout)  # type: ignore[arg-type]
    elapsed = time.monotonic() - start
    log_usage(args.model, str(plan["sandbox"]), elapsed, code)
    summary = change_summary()

    if args.json:
        print(
            json.dumps(
                {
                    "exit": code,
                    "sandbox": plan["sandbox"],
                    "output": output,
                    "changes": summary,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(output or f"(no output; exit {code})")
        print(
            f"\n--- sandbox={plan['sandbox']} exit={code} elapsed={elapsed:.1f}s ---",
            file=sys.stderr,
        )
        if summary["status"]:
            print(f"--- changes ---\n{summary['status']}", file=sys.stderr)
    return code if code in (0, 2, 3, 4) else code


if __name__ == "__main__":
    raise SystemExit(main())
