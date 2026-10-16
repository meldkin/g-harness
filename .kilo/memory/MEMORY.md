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
- [decision] CommandCode model ids are verified against
  `GET {COMMANDCODE_BASE_URL}/models`, never from memory. Each consumer declares models
  separately: `_PROVIDER_MODELS` in `tools/opencode_engine.py` (OpenCode uses the harness
  key `commandcode/deepseek-v4-pro`), `.vscode/settings.json` (Copilot), and
  `~/.config/kilo/kilo.jsonc` (Kilo uses the full upstream id
  `commandcode/deepseek/deepseek-v4-pro`). `context_length` comes from the response, not
  the file. (2026-09-28; catalog 80 model on 2026-10-16)
- [decision] Guard hardening (2026-10-07): 33 -> 41 destructive patterns, 8 holes closed,
  list in `decisions-archive.md`. (2026-10-16) re-measured: 5 of 7 already fixed; 3 of the 4
  left closed (+3 Windows-root patterns -> 44, README synced; quoted spans holding a
  separator read as data). The 4th (secrets in a Kilo command unscanned) stays open: fixing
  it needs `hooks.json` or a JS secret list. Pipeline drills `bcfa6bd`+`c2e174f` closed the
  wrapper gap and round 2's 2 regressions; 10 quoting gaps remain (archive). Pytest timeout
  120 -> 300s.
- [decision] dsh worker verified (2026-10-07, re-verified 2026-10-16 `DSH_ARM_OK`): detail and
  prerequisites in `decisions-archive.md`.
- [decision] Pipeline 4 vai trò (2026-10-16): Jev (agent trên **model JEV**
  `openrouter/jev-router`) điều phối; **Codex** ra đề bài + **verify** (`gpt-6.1-sol`,
  effort `medium`, đổi bằng `--model`/`--effort`); **DeepSeek V4.1 Flash** (OpenCode CLI,
  + `dsh`) code sâu; **Gemini 3.8 Flash** (Antigravity CLI) việc nhanh nhẹ. Fallback:
  Codex không ổn định → DeepSeek viết brief + thẩm định lại Gemini. Jev `edit: deny` và
  wrapper chạy agent này **không `--auto`** để deny có hiệu lực. Gotcha: timeout mặc định
  của wrapper opencode/agy là **120s** → job dài bị giết oan (đã nâng 900/600); `.ps1` tải
  về bị mark-of-the-web → phải `Unblock-File`. Catalog **80 model / 4 provider**.
- [decision] G7 control plane (2026-10-15): `session_registry.py` +
  `session_control.py` (`list`/`send`/`interrupt`/`prune`); cả 5 delegate đã ghi
  registry (seam `Popen`→`record_start(pid)`→`kill_tree` khi timeout). **Race thật**:
  interrupt bị ghi đè thành `exited` → claim `interrupting` trước khi giết.
  `send_message` chỉ cho phiên khai báo kênh (hiện chưa có).
- [decision] Docs gộp (2026-10-16): 8 báo cáo lịch sử (upgrade-summary, audit-08-15,
  audit-09-04, 5 file cross-review) vào
  `docs/archive-harness-upgrade-review-and-audit-reports-2026.md` verbatim; 8 file gốc
  thành con trỏ. Giữ standalone `deepseek-harness-upgrade-acceptance.md` +
  `audit-2026-09-11.md`. garden.py bỏ qua docs trong `docs/` mà tên chứa review/report.
- [decision] Parity launcher ↔ delegate về biến môi trường (2026-10-16): chỉ cắt `/v1` ở biến mà
  config sinh ra **thêm** `/v1` — hiện chỉ `OPENAI_BASE_URL`; `COMMANDCODE_BASE_URL` và
  `DEEPSEEK_BASE_URL` dùng **nguyên văn**. Cắt `/v1` của commandcode từng làm mọi call delegate
  hỏng (A/B cùng call: `Unknown error` → `OK` 8.2s). `tools/test_env_file.py` suy luật **từ chính**
  `.opencode/opencode.json`, nên thêm provider có template `/v1` là test đỏ ngay. Ghi chú: launcher
  xuất **mọi** key `.env` bằng vòng lặp chung nên nó và `env_file.py` đã ngang nhau — audit chỉ grep
  `$env:NAME =` sẽ báo thiếu biến oan.
- [decision] Nhận diện "harness cũ" ở target (2026-10-16): theo **nội dung** cho `SPEC.md` (marker
  harness ghi ở dòng đầu) và theo **đúng tên** cho `docs/`; **không bao giờ** theo sự tồn tại hay
  tên đơn thuần — `SPEC.md` và `docs/` là project-owned (deploy không được xoá). Chỉ liệt kê 22/27
  tên tài liệu v4.1.0; bỏ `README.md`, `evaluation-report.md`, `capability-seams.md`,
  `code-review-checklist.md`, `defensive-patterns.md` vì dự án cũng có thể sở hữu tên đó. Note chỉ
  **báo tên**, không xoá gì.
- [decision] Bất đối xứng store credential (2026-10-16, chủ dự án quyết "để nguyên"):
  `opencode-env.ps1` đăng xuất credential `freemodel` đã lưu mỗi lần chạy (key lưu sẵn che key
  `.env`), `tools/opencode_delegate.py` **không** đụng store. Hôm nay chưa đo được lỗi vì FreeModel
  đang lấy từ env → không mirror, chỉ ghi nhận; nếu về sau delegate báo Unauthorized với freemodel
  thì đây là nguyên nhân đầu tiên cần loại trừ.
- [decision] Hợp nhất một nguồn GitHub (2026-10-16, chủ dự án quyết): repo chính là
  `solo-code-com/Solo-Code-Harness` — giữ 3 sao + 1 fork, vì sao/rating gắn với **repo** chứ không
  gắn branch nên ghi đè `main` không làm mất. Mốc cũ `6f261bd` (208 commit) đã đẩy lên đó dưới nhánh
  Do force-push bị guard chặn (agent không được lách), việc đồng bộ đã làm bằng **fast-forward**:
  commit `ae754e7` có tree **y hệt** bộ mới (`b2aa4ae`) và parents = [mốc cũ, `main` của ta] ⇒ 208
  commit cũ vào thẳng lịch sử chứ không bị mồ côi. Bản `reference\Solo-Code-Harness-main` đã xoá —
  không file nào tham chiếu nó, object cũ vẫn ở `.git` local qua ref `oldharness/main`.
