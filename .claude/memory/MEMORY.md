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
- [decision] Antigravity headless `agy.exe` delegate re-established (2026-10-06);
  runs through `tools/antigravity_delegate.py` (read-only default, writes need
  `--allow-dir` + `--auto-approve` with a shared-state lock and scope audit), tiers
  `gemini-3.8-flash-{low,medium,high}`. Quota rotation and auth details are in
  `decisions-archive.md`.
- [decision] Antigravity headless permission behavior (measured 2026-10-06): exit codes
  and flag caveats are archived verbatim in `decisions-archive.md`.
- [decision] OpenCode avoids duplicate skill mirrors and uses Claude-compatible
  skills.
- [decision] Codex lifecycle and guard behavior is launcher-based, because Codex
  has no project hooks. Of the gateway's aliases only `gpt-5.6-terra` routes
  reproducibly; the rest are unstable or dead — measurements and traps are in
  `decisions-archive.md` (2026-09-14).
- [decision] CommandCode model ids are verified against
  `GET {COMMANDCODE_BASE_URL}/models`, never from memory. Each consumer declares models
  separately: `_PROVIDER_MODELS` in `tools/opencode_engine.py` (OpenCode uses the harness
  key `commandcode/deepseek-v4-pro`), `.vscode/settings.json` (Copilot), and
  `~/.config/kilo/kilo.jsonc` (Kilo uses the full upstream id
  `commandcode/deepseek/deepseek-v4-pro`). `context_length` comes from the response, not
  the file. (2026-09-28; catalog 80 model on 2026-10-16)
- [decision] Subagent `ask` permission behaves as `allow` (measured,
  operator-confirmed 2026-10-07): a headless child session has no prompt
  channel, so `effect: ask` silently permits -- the operator saw no dialog
  appear during a two-command probe. Use explicit `allow`/`deny`; never `ask`.
- [decision] Guard hardening (2026-10-07): 33 -> 41 destructive patterns, 8 verified
  holes closed, Codex review rounds; the full finding list is in `decisions-archive.md`.
  The checklist Pytest timeout rose 120s -> 300s (suite ~95-130s on Windows).
- [decision] Coverage (2026-10-07): the 13 files that started at 0.0% have tests and
  raised baselines; detail in `decisions-archive.md`.
- [decision] GUI worker console (2026-10-07): full detail in `decisions-archive.md`
  (loopback-only stdlib web app in `tools/gui_server.py`, `.env` key NAMES only).
- [decision] dsh worker verified (2026-10-07): detail in `decisions-archive.md`.
- [decision] Pipeline 4 vai trò (2026-10-16): Jev (agent trên **model JEV**
  `openrouter/jev-router`) điều phối; **Codex** ra đề bài + **verify** (`gpt-6.1-sol`,
  effort `medium`, đổi bằng `--model`/`--effort`); **DeepSeek V4.1 Flash** (OpenCode CLI,
  + `dsh`) code sâu; **Gemini 3.8 Flash** (Antigravity CLI) việc nhanh nhẹ. Fallback:
  Codex không ổn định → DeepSeek viết brief + thẩm định lại Gemini. Jev `edit: deny` và
  wrapper chạy agent này **không `--auto`** để deny có hiệu lực. Gotcha: timeout mặc định
  của wrapper opencode/agy là **120s** → job dài bị giết oan (đã nâng 900/600); `.ps1` tải
  về bị mark-of-the-web → phải `Unblock-File`. Catalog **80 model / 4 provider**.
- [decision] Codex worker arm (2026-10-07): full detail in `decisions-archive.md`
  (read-only sandbox by default, brief in a file, post-run git status/diffstat).
- [decision] Subagent seam implemented (2026-10-07): `tools/subagent_cli.py` provides
  the Protocol in `tools/subagent_seam.py`; `write` is deliberately not advertised.
  Version 4.3.0; full detail in `decisions-archive.md`.
- [decision] Subagent reviewers hold `read` + `edit`, no shell for `code-reviewer`
  (2026-10-07). Garden's "Permission drift" and "Agent tools drift" checks, and the
  filename-only `check_agents` they replaced, are in `decisions-archive.md`.
- [decision] Worker confinement mechanism (2026-10-14): `tools/win_sandbox.py` —
  Windows ACL restricted token, `--also-write` để cấp thêm root ghi, `revert` để gỡ
  ACE; verify bằng `icacls`. Gotcha: đường CLI chỉ chạy qua subprocess thì coverage
  không thấy. Budget: giữ số keyless của `test_e2e`.
- [decision] G5 dừng ở nhánh restricted-token (2026-10-15): `win_sandbox.py` chặn
  ghi đúng (40 test) **nhưng HTTPS/TLS fail dưới token hạn chế**
  (`SEC_E_NO_CREDENTIALS`) ⇒ không bọc được worker nào của fleet (mọi worker gọi
  API). `--confine` trong `codex_delegate` bị chặn có chủ ý; nếu cần cách ly →
  AppContainer (chưa làm). Việc kế: G7/P2.2 (spec `plan.md` §4.1).
- [decision] G7 control plane (2026-10-15): `session_registry.py` +
  `session_control.py` (`list`/`send`/`interrupt`/`prune`); cả 5 delegate đã ghi
  registry (seam `Popen`→`record_start(pid)`→`kill_tree` khi timeout). **Race thật**:
  interrupt bị ghi đè thành `exited` → claim `interrupting` trước khi giết.
  `send_message` chỉ cho phiên khai báo kênh (hiện chưa có).
