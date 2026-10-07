# Memory Index

High-signal context loaded at session start. Detailed history belongs in
`decisions-archive.md`; keep this file below the 8,000-character gate.

## Project
- [project] Branches: `feature/[task-slug]` or `fix/[bug-slug]`.
- [project] `AGENTS.md` is the root rulebook; `.harness.lock` defines boundaries.
- [project] `.kilo/` is source of truth. Claude and OpenCode are generated from
  it; Copilot/Gemini are parity-checked.

## Rules
- [rules] Read before editing; make surgical changes; verify syntax and tests.
- [rules] User input is untrusted. Parameterize SQL; keep credentials in env vars.
- [rules] Ask before destructive actions, dependency installs, CI changes, or
  deletion.
- [rules] Use `permission-guard`; executor mode is ON by default. Run the
  security scan before committing.

## Tech Stack
- [tech] Python 3.10+ stdlib runtime for `tools/` and `.github/scripts/`;
  pytest/ruff are dev tools. Kilo hooks use Node.js 18+.
- [tech] Ruff config: `.ruff.toml`; secrets: `.gitleaks.toml`.
- [tech] Codex CLI 0.160.0 (npm global) is a harness consumer: it reads
  `AGENTS.md` natively, so no `.codex/` engine mirror is generated. Launcher
  `codex-env.ps1`, metering `tools/codex_usage.py`.
- [tech] SQLite shared state: `.solocode/shared-state.db`. Only `session_log`
  actually has rows; `features` and `shared_memory_*` exist but are unused —
  git log plus this file cover task tracking and conventions. `codex` is a
  valid engine name in `tools/shared_state.py`.

## Verification
- [verify] Full Codex gate: `python tools/codex_verify.py`.
- [verify] Individual gates: security scan, schema validation, garden,
  no-skips, pytest.
- [verify] Codex has no repository hook API, so use `tools/codex_guard.py` for
  destructive-command, secret, and file-lock preflight checks, or run
  verified writes with `tools/codex_guard.py --write`.

## Gotchas
- [gotcha] Bare Codex does not load `.env`; always run via the launcher.
- [gotcha] Codex gateway needs `code_mode.enabled = false`,
  `unified_exec = false`, `wire_api = "responses"`, and a full-access sandbox.
- [gotcha] Codex base URLs do not interpolate `${VAR}`; the launcher passes a
  `-c model_providers.<id>.base_url=...` override instead.
- [gotcha] Codex CLI internal exec policy blocks `rm -f` / `-Force` patterns;
  under `approval_policy = "never"` this aborts process creation. Avoid `-Force`
  in PowerShell, or use `python tools/codex_guard.py --write`.
- [gotcha] TOML bare keys must precede the first table header.
- [gotcha] Keep loaded memory under 8,000 chars. MOVE pruned material into
  `decisions-archive.md` verbatim — never silently delete it.
- [gotcha] `.pytest_temp` cleanup can race on Windows; rerun pytest if needed.
- [gotcha] `check_lint_budget` honours `.gitignore` only when the tree is a git
  repo. Without `.git/`, ruff still scans `.pytest_temp*/` and the count overshoots
  the budget (measured 49 vs 45 on the pristine tree). Run `git init` before
  trusting the gate.

## Decisions
- [decision] Antigravity headless `agy.exe` delegate **re-established** after
  the retirement rationale was disproven: the account lockouts were a
  Google-side update bug, not bot-traffic flags from `agy.exe`; the accounts
  were reopened and the CLI was never implicated (2026-10-06). Worker runs
  through `tools/antigravity_delegate.py` — read-only by default, writes need
  `--allow-dir` + `--auto-approve` with a shared-state directory lock and
  post-run scope audit. Model is chosen by task complexity via the distinct ids
  `gemini-3.8-flash-{low,medium,high}`. Quota rotation is manual: `agy.exe`
  uses the machine-level Antigravity Google account and has no per-run account
  flag; switch account with `/logout` then re-sign-in, check quota with `/usage`,
  and resume with `--conversation <id>` or `--continue-latest`. A Gemini API key
  (`modelProvider: "gemini"` + `GEMINI_API_KEY`) is the headless alternative.
  Auth/settings details and doc links are in `decisions-archive.md`.
- [decision] Antigravity headless permission behavior (measured 2026-10-06 on
  `agy.exe` 1.2.9): the exit codes (5 on denied actions, 2 on empty output), the
  `--allow-tools` flag and its mutual exclusions, and the `view_file` /
  `grep_search` caveats are archived verbatim in `decisions-archive.md`.
- [decision] OpenCode avoids duplicate skill mirrors and uses Claude-compatible
  skills.
- [decision] Codex lifecycle and guard behavior is launcher-based, because Codex
  has no project hooks. Of the gateway's aliases only `gpt-5.6-terra` routes
  reproducibly; the rest are unstable or dead — measurements and traps are in
  `decisions-archive.md` (2026-09-14).
- [decision] CommandCode model ids are verified against
  `GET {COMMANDCODE_BASE_URL}/models`, never from memory: the catalog drifts and
  the old `api-providers.md` advertised nine ids that no longer resolve. Each
  CommandCode consumer declares models separately, so a new model needs one entry
  in `tools/opencode_engine.py` `_PROVIDER_MODELS` (OpenCode), `.vscode/settings.json`
  (Copilot), and `~/.config/kilo/kilo.jsonc` (Kilo). Kilo refs use the full
  upstream id (`commandcode/deepseek/deepseek-v4-pro`) while OpenCode refs use the
  harness key (`commandcode/deepseek-v4-pro`) — both correct for their dialect.
  `context_length` comes from the `/models` response, not the file. (2026-09-28)
- [decision] Subagent `ask` permission behaves as `allow` (measured,
  operator-confirmed 2026-10-07): a headless child session has no prompt
  channel, so `effect: ask` silently permits -- the operator saw no dialog
  appear during a two-command probe. Use explicit `allow`/`deny`; never `ask`.
- [decision] Guard hardening (2026-10-07): 33 -> 41 destructive patterns in
  `.claude/hooks/guard.py` + `.kilo/hooks/pre-tool-use/gate-guard.js`. Eight
  verified holes closed; independent Codex (gpt-6.1-sol) review rounds ran,
  and every self-inflicted regression they found was fixed (over-blocks on quoted
  searches / `./build` / `..`-named files; `bash -c` and wrapped-`curl|bash`
  divergences). New patterns anchor to command position, and Kilo gained a
  `normalizeCommand` port so both engines unwrap `sudo`/`env`/`bash -c` alike.
  Pre-existing gaps still open, and the full finding list, are in
  `decisions-archive.md`. The checklist Pytest timeout rose 120s -> 300s (suite
  ~95-130s on Windows).
- [decision] Coverage (2026-10-07): every file that started at 0.0% (13 total)
  now has tests and the ratchet baseline is raised. `pre-commit` is installed and
  its git hook is active.
- [decision] GUI worker console (2026-10-07): a stdlib-only local web app
  (`tools/gui_server.py` + `tools/gui/index.html`, test `tools/test_gui_server.py`)
  that discovers worker CLIs (agy/opencode/kilo/dsh/codex) + their wrappers, lists
  the provider/model catalog and `.env` key NAMES (never values), and runs a brief
  through the matching `*_delegate.py`. Loopback-only, per-run token, worker+model
  allowlist. Codex is wired too (`tools/codex_delegate.py`, read-only default).
- [decision] Codex worker arm (2026-10-07): `tools/codex_delegate.py` runs Codex
  through `codex-env.ps1` with a read-only sandbox by default (`--allow-write` ->
  workspace-write; the dangerous flags are never emitted), writes the guardrail
  brief to a file because the Windows npm shim truncates multi-line arguments, and
  returns a post-run git status/diffstat. Codex has no project hooks, so
  `tools/codex_guard.py` stays the separate preflight.
- [decision] Subagent seam implemented (2026-10-07): `tools/subagent_cli.py` is
  the Provider for the Protocol in `tools/subagent_seam.py` — a `CliProvider` over
  the delegate wrappers (evidence split from summary) plus a capability/rank
  dispatcher; `write` is deliberately not advertised. Harness version bumped to
  4.3.0 across `.harness.lock`, `agent.yaml` and `pyproject.toml`.
- [decision] Subagent reviewers hold `read` + `edit`, no shell for
  `code-reviewer`. Garden gained "Permission drift" (agent `permission:` block
  vs `.copilot`/`.gemini`) and "Agent tools drift" (derived `.claude` `tools:`);
  the old `check_agents` compared filenames only and reported clean while the
  engines disagreed (2026-10-07).
