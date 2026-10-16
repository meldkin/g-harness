#!/usr/bin/env python3
"""One-shot worker over a provider's chat-completions endpoint.

Why this exists: the CLI workers pay for a tool loop the orchestrator has already walked. A
measured Kilo run spent 1200-1557 seconds on a brief that named the files and the exact change,
most of it re-reading the repo and re-running tests that had already been run; OpenCode spent
78-871 seconds and failed outright twice in seven calls. For a brief that is already precise, a
single completion returns the patch in seconds -- and the worker never writes the repo, so the
orchestrator applies and verifies it.

Routing (operator's rule, 2026-10-16): GPT-family models go through `codex-env.ps1`, Gemini
models through the Antigravity CLI, and DeepSeek over this one-shot path when the task is
brief-shaped. Work that genuinely needs the loop (explore, edit many files, iterate until tests
pass) stays with the Kilo/OpenCode CLI arms.

Usage:
    python tools/model_api.py "explain the diff" --include src/app.py
    python tools/model_api.py --prompt-file .solocode/scratch/brief.md --out patch.md
    python tools/model_api.py - --model commandcode/deepseek/deepseek-v4.1-flash-fast < prompt.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import env_file  # noqa: E402

ROOT = TOOLS_DIR.parent
#: The vendor-prefixed id: this endpoint rejects the harness's short key form with
#: `unsupported_model` (measured 2026-10-16), so the full upstream id is what goes on the wire.
DEFAULT_MODEL = "commandcode/deepseek/deepseek-v4.1-flash"
USAGE_LOG = ROOT / ".solocode" / "model-api-usage.jsonl"

GUARDRAIL = """\
You are a worker invoked by an orchestrator. Return only the artefact it asked for - code,
a unified diff, or the requested answer - with no preamble and no self-assessment. Constraints
you must respect: (1) do not invent APIs or file paths; if the request is underspecified, say
so in one line instead of guessing; (2) if you return code, return it complete enough to apply,
and state the exact file paths you would touch; (3) never assume you can run commands or read
files you were not given.
"""


def log_usage(record: dict) -> None:
    """Append one usage line, so a direct call is accounted for like a CLI run."""
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def call_model(
    model_ref: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> tuple[str | None, dict, str]:
    """POST one completion. Returns (content, usage, error)."""
    provider, _, model_id = model_ref.partition("/")
    if not model_id:
        return None, {}, f"model must be <provider>/<model-id>, got {model_ref!r}"
    try:
        url, key = env_file.provider_endpoint(provider, "chat")
    except KeyError as exc:
        return None, {}, str(exc)
    if not url or not key:
        return None, {}, f"missing base url or {provider} credential in .env"
    payload = json.dumps(
        {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - operator-configured https endpoint
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "opencode/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200].replace("\n", " ")
        return None, {}, f"HTTP {exc.code}: {detail}"
    except Exception as exc:  # noqa: BLE001 - any transport failure is reported, never raised
        return None, {}, type(exc).__name__
    usage = body.get("usage") or {}
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return None, usage, f"unexpected body: {json.dumps(body)[:160]}"
    content = message.get("content") or message.get("reasoning_content") or ""
    return content, usage, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot worker over a provider's chat API"
    )
    parser.add_argument("prompt", nargs="?", help="the task; '-' reads stdin")
    parser.add_argument("--prompt-file", help="read the task from a file instead")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"<provider>/<model-id> (default {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="FILE",
        help="inline a file's contents (repeatable)",
    )
    parser.add_argument("--out", help="write the answer here as well as stdout")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--no-guardrail", action="store_true", help="omit the worker preamble"
    )
    parser.add_argument(
        "--json", action="store_true", help="print a JSON result object"
    )
    args = parser.parse_args(argv)

    env_file.load_project_env()

    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("a prompt, --prompt-file or '-' is required")

    for rel in args.include:
        path = Path(rel)
        if not path.is_file():
            print(f"[model_api] include not found: {rel}", file=sys.stderr)
            return 2
        prompt += f"\n\n--- file: {rel} ---\n{path.read_text(encoding='utf-8')}"

    messages = []
    if not args.no_guardrail:
        messages.append({"role": "system", "content": GUARDRAIL})
    messages.append({"role": "user", "content": prompt})

    started = time.monotonic()
    content, usage, error = call_model(
        args.model,
        messages,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout=args.timeout,
    )
    elapsed = time.monotonic() - started
    ok = bool(content) and not error

    log_usage(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": args.model,
            "prompt_chars": len(prompt),
            "includes": args.include,
            "elapsed_s": round(elapsed, 2),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "ok": ok,
            "error": error or None,
        }
    )

    if not ok:
        print(
            f"[model_api] failed after {elapsed:.1f}s: {error or 'empty response'}",
            file=sys.stderr,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": error or "empty response",
                        "seconds": round(elapsed, 2),
                    }
                )
            )
        return 2

    if args.out:
        # Models habitually wrap an artefact in a ```diff fence; strip it before saving so the
        # file is apply-able. The hunk headers may still need a manual fix: measured 2026-10-16,
        # one logically correct patch carried `+N,13` for a 12-line body and a start line ~29 off,
        # which `git apply` rejects even with --recount.
        clean = content
        stripped = clean.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines) + "\n"
        Path(args.out).write_text(clean, encoding="utf-8", newline="\n")
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "model": args.model,
                    "seconds": round(elapsed, 2),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "out": args.out,
                    "content": content,
                }
            )
        )
    else:
        sys.stdout.write(content if content.endswith("\n") else content + "\n")
    print(
        f"[model_api] {args.model} ok in {elapsed:.1f}s ({usage.get('completion_tokens')} completion tokens)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
