#!/usr/bin/env python3
"""Run the DeepSeek Harness (dsh) as a worker in a sibling checkout.

dsh lives in `reference/deepseek-harness-master/` and runs from source with
`pnpm dsh --profile <name> "<task>"`. This wrapper locates that checkout, loads
`DEEPSEEK_API_KEY` from the project `.env`, runs the task, and returns its output.

This wrapper injects NO guardrail prompt, takes no directory lock, and runs no
post-run scope audit -- unlike `antigravity_delegate.py`. Whatever the task can
write, it writes: containment comes from the dsh profile it launches, not from
this file. Pass a read-only profile if you need read-only.

UNVERIFIED: dsh has not been installed or built on this machine beyond checking
that its prerequisites (Node >= 22.19, pnpm) are satisfied, so this wrapper's
execution path has not been exercised end to end. `--self-test` covers argument
handling and checkout resolution only. Confirm with a real run before relying on
it.

Usage:
    python tools/dsh_delegate.py --self-test
    python tools/dsh_delegate.py "<self-contained task>"
    python tools/dsh_delegate.py "<task>" --profile headless --timeout 600
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # noqa: S404 — runs this checkout's own pinned launcher
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT_SECONDS = 600

# Minimal environment variable names dsh reads for a real run.
ENV_KEYS = ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL")


def _stderr(message: str) -> None:
    print(f"[dsh_delegate] {message}", file=sys.stderr)


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE .env file; return {} when it is absent or unreadable."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def find_dsh_dir(explicit: str | None = None) -> Path | None:
    """Resolve the dsh checkout from an explicit path, DSH_DIR, or known candidates."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_dir = os.environ.get("DSH_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates += [
        ROOT.parent / "reference" / "deepseek-harness-master",
        ROOT.parent / "deepseek-harness-master",
        ROOT.parent.parent / "reference" / "deepseek-harness-master",
    ]
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "package.json").is_file() and (resolved / "packages").is_dir():
            return resolved
    return None


def dsh_script_declared(dsh_dir: Path) -> bool:
    """True when the checkout's package.json declares a `dsh` script."""
    import json

    try:
        data = json.loads((dsh_dir / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    scripts = data.get("scripts")
    return isinstance(scripts, dict) and "dsh" in scripts


def build_command(pnpm: str, profile: str, task: str) -> list[str]:
    """Build the dsh source-launch command. Task is a single positional arg."""
    return [pnpm, "dsh", "--profile", profile, task]


def run_dsh(
    *, command: list[str], dsh_dir: Path, env: dict[str, str], timeout_s: int
) -> tuple[int, str, str]:
    """Execute dsh and return (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(  # noqa: S603 — argv built here, no shell
            command,
            cwd=dsh_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"Timeout after {timeout_s}s"
    except OSError as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _self_test() -> int:
    """Exercise argument handling and checkout resolution without running dsh."""
    failures: list[str] = []

    command = build_command("pnpm", "headless", "do a thing")
    if command != ["pnpm", "dsh", "--profile", "headless", "do a thing"]:
        failures.append(f"build_command produced {command!r}")

    if build_command("pnpm", "headless", "a\nb")[-1] != "a\nb":
        failures.append("task with a newline was not kept as one argument")

    env_sample = Path(__file__).parent / "nonexistent.env"
    if load_env_file(env_sample) != {}:
        failures.append("load_env_file should return {} for a missing file")

    resolved = find_dsh_dir(None)
    if resolved is not None and not (resolved / "packages").is_dir():
        failures.append(f"find_dsh_dir returned a non-checkout: {resolved}")

    if failures:
        for item in failures:
            _stderr(f"SELF-TEST FAIL: {item}")
        return 1
    print("self-test OK")
    print(f"dsh checkout: {resolved if resolved else 'NOT FOUND'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeepSeek Harness delegation wrapper")
    parser.add_argument("prompt", nargs="?", help="Self-contained task for dsh")
    parser.add_argument("--profile", default="headless", help="dsh profile (default: headless)")
    parser.add_argument("--dsh-dir", help="Path to the dsh checkout (default: auto-detect)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--self-test", action="store_true", help="Validate setup without running dsh")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.prompt:
        parser.error("a task prompt is required unless --self-test is given")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    dsh_dir = find_dsh_dir(args.dsh_dir)
    if dsh_dir is None:
        _stderr(
            "dsh checkout not found. Pass --dsh-dir, set DSH_DIR, or place the "
            "checkout at reference/deepseek-harness-master."
        )
        return 1
    if not dsh_script_declared(dsh_dir):
        _stderr(f"{dsh_dir}/package.json declares no `dsh` script; wrong checkout?")
        return 1

    pnpm = shutil.which("pnpm")
    if not pnpm:
        _stderr("pnpm not found on PATH; dsh runs from source through pnpm.")
        return 1

    env = os.environ.copy()
    for key, value in load_env_file(ROOT / ".env").items():
        if key in ENV_KEYS and value:
            env[key] = value
    # Only the API key is required; DEEPSEEK_BASE_URL is loaded when present but
    # has a working default, so it is not part of the missing check.
    missing = ["DEEPSEEK_API_KEY"] if not env.get("DEEPSEEK_API_KEY") else []
    if missing:
        _stderr(f"{', '.join(missing)} not set; dsh needs it to call a model.")
        return 1

    command = build_command(pnpm, args.profile, args.prompt)
    _stderr(f"dsh_dir={dsh_dir} profile={args.profile} timeout={args.timeout}s")
    code, out, err = run_dsh(
        command=command, dsh_dir=dsh_dir, env=env, timeout_s=args.timeout
    )
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        _stderr(err.strip()[:1000])
    if code != 0:
        _stderr(f"dsh exited with code {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
