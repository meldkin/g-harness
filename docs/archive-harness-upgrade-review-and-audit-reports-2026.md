# Archive ? harness upgrades and verification audits (2026)

> Consolidated 2026-10-16 from eight point-in-time reports that `docs/README.md` already
> classified as `Historical Archive`. Each section below reproduces one source document
> verbatim under a `Source:` heading; the original files now hold a short pointer back to
> this archive, and git keeps their earlier history.
>
> **Every number in here is a snapshot, not a current fact.** Measured drift when this
> archive was assembled: pytest 452-544 passed (now ~1262), security scan 579-2518 files
> (now 916), schema 64-66 files (now 68), lint budget 46-60 (now 45), skills/agents 50/14
> (now 53/15), executor described as "OpenCode CLI only" (now a five-worker fleet), active
> locks 1 (now 0), and SQLite's `features` table as the primary state store (overturned by
> Plan B: `git log` + `.kilo/memory/MEMORY.md`).
>
> Two documents from the same period were deliberately **not** archived, because they are
> still load-bearing: [`deepseek-harness-upgrade-acceptance.md`](deepseek-harness-upgrade-acceptance.md)
> (the formal acceptance record) and [`audit-2026-09-11.md`](audit-2026-09-11.md)
> (the F1-F10 consistency spec cited by the handoff and by the tests).

## 1. Executive timeline

| When | Milestone | Source |
|---|---|---|
| Aug 14-15 | Weeks 1-4 re-architecture; DeepSeek harness Tier A port | `upgrade-summary.md`, `audit-2026-08-15.md` |
| Sep 4 | Benchmark-executor fixes, Windows pytest `--basetemp`, garden doc-scan bugs | `audit-2026-09-04.md` |
| Sept | DeepSeek upgrade cross-review: plan, two response rounds, follow-up, final concurrence | the four dossier files below |

---

## 2. Weeks 1-4 re-architecture summary

### Source: `docs/upgrade-summary.md`

> Moved here verbatim on 2026-10-16.

# Solo-Code-CLI Upgrade Summary

**Completion Date**: 2026-08-14
**Orchestrator**: Claude Code (Sonnet 5)
**Executor**: OpenCode CLI (DeepSeek V4 Pro)

---

## 🎯 Weeks 1-4 HOÀN THÀNH

### Week 1: Testing Infrastructure ✅

**Objective**: Establish comprehensive testing framework with keyless support

| Task | File | Lines | Commit | Status |
|------|------|-------|--------|--------|
| 1.1 Snapshot Testing | `tools/snapshot_testing.py` | 284 | 8c4acf1 | ✅ |
| 1.2 Coverage Gate | `tools/coverage_gate.py` | 271 | 886756d | ✅ |
| 1.3 E2E Testing | `tools/test_e2e.py` | 344 | 2194ddc | ✅ |
| Guard Tests | `tools/test_guard.py` | 48 | 2d4ae27 | ✅ |

**Key Features**:
- Snapshot testing with record/replay mechanism
- Coverage ratcheting (never regress)
- Self-skip E2E tests when no API key
- Guard hook validation suite

---

### Week 2: Security & Safety Gates ✅

**Objective**: Defensive programming and secret protection

| Task | File | Lines | Commit | Status |
|------|------|-------|--------|--------|
| 2.1 Guard Hooks | `.claude/hooks/guard.py` | existing | verified | ✅ |
| 2.2 Security Post-Hook | `.claude/hooks/security_post.py` | existing | verified | ✅ |
| 2.3 Defensive Patterns | `docs/defensive-patterns.md` | 293 | a3e1c8f | ✅ |

**Key Features**:
- Destructive command blocking
- Secret pattern detection
- Protected config prevention
- Subprocess safety documentation

---

### Week 3: Quality Gates & Standards ✅

**Objective**: Automated quality enforcement

| Task | File | Lines | Commit | Status |
|------|------|-------|--------|--------|
| 3.1 Prose Quality | `.claude/hooks/quality_gate.py` | existing | 849e26a | ✅ |
| 3.2 Pre-Push Hook | `.claude/hooks/pre_push.py` | 124 | 4a0288d | ✅ |
| 3.3 Review Checklist | `docs/code-review-checklist.md` | 157 | 8aa3710 | ✅ |

**Key Features**:
- 6-gate pre-push verification (ruff, budget, schema, garden, pytest, security)
- Markdown prose quality checks
- Systematic code review template (60+ items)

---

### Week 4: Session Management ✅

**Objective**: Cross-session persistence and analytics

| Task | File | Lines | Commit | Status |
|------|------|-------|--------|--------|
| 4.1 Persistence | `tools/session_persistence.py` | 427 | 97bbbbf | ✅ |
| 4.2 Analytics | `tools/session_analytics.py` | 375 | bb86874 | ✅ |
| 4.3 Integration | `.claude/hooks/session_*.py` | - | eb243f3 | ✅ |

**Key Features**:
- SQLite database (`.solocode/sessions.db`)
- Session tracking (start_time, end_time, branch, files_changed)
- Analytics (list, search, stats, recent, by-branch)
- Auto-integration with SessionStart/SessionEnd hooks

---

## Metrics Achieved

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Test Coverage | 100% core | ~85% | 🟡 In Progress |
| Secrets Leaked | 0 | 0 | ✅ Pass |
| All Gates Pass | 6/6 | 6/6 | ✅ Pass |
| Session Tracking | SQLite | SQLite | ✅ Implemented |
| Gate Suite Speed | <5 min | ~2 min | ✅ Pass |
| Lint Budget | No increase | 46→56 | 🟡 Justified |

**Lint Budget Note**: Increase from 46 to 56 findings justified by Week 2 harness expansion (hooks, tools, scripts). All new findings pre-reviewed and from infrastructure code, not application code.

---

## Implementation Stats

**Total Commits**: 12
**Total Lines Added**: ~2,643
**Total Lines in New Files**: ~3,074
**Duration**: Week 1-4 (Aug 2026)

**Files Created**:
```
tools/
├── snapshot_testing.py      (284 lines)
├── coverage_gate.py         (271 lines)
├── test_e2e.py             (344 lines)
├── test_guard.py           (48 lines)
├── session_persistence.py   (427 lines)
└── session_analytics.py     (375 lines)

.claude/hooks/
└── pre_push.py             (123 lines)

docs/
├── defensive-patterns.md    (293 lines)
└── code-review-checklist.md (157 lines)
```

---

## Orchestrator-Executor Pattern

**Primary Executor**: OpenCode CLI (DeepSeek V4 Pro)
**Fallback Strategy**: Direct implementation when timeout (120s)
**Executor Mode**: Toggle via `.solocode/executor-mode` (on/off)

**Delegation Flow**:
1. Plan task with file paths and requirements
2. Delegate to OpenCode CLI: `python tools/opencode_delegate.py "<task>" --free`
3. Verify result: read files back, run gates, check git diff
4. Never trust self-summary: workers can misreport

**Success Rate**:
- OpenCode CLI tasks: 8/10 completed (2 timeouts)
- Fallback to direct: 2/10 tasks
- Verification caught: 100% of misreports

---

## Key Learnings

### 1. Verification is Mandatory
Every OpenCode CLI execution produced correct code BUT self-summary had inaccuracies:
- Claimed file paths that didn't exist
- Reported features not actually implemented
- Missed edge cases in own code

**Solution**: Always verify with independent commands (cat, git diff, pytest)

### 2. Lint Budget Ratcheting Works
Budget increased only once (46→56) with full justification:
- All new findings from harness infrastructure
- Pre-reviewed security patterns (subprocess calls, exception handling)
- Documented in commit message

**Principle**: Lower as bugs are fixed, raise only for justified infrastructure expansion

### 3. Fallback Strategy is Essential
OpenCode CLI timeouts (2 cases):
- Task 3.2: Pre-push hook (120s timeout)
- Switched to direct implementation via fallback

**Pattern**: Disable executor mode, implement directly, re-enable after completion

### 4. Hook Integration Complexity
Session persistence required careful integration:
- Import path issues (`sys.path` manipulation needed)
- Error handling (log to file, don't crash session)
- State validation (create dirs, init DB on first use)

**Solution**: Defensive programming at every boundary

---

## What Worked Well

1. **Orchestrator-Executor Pattern**: Clear separation of planning (Claude) and execution (OpenCode)
2. **Verification Gates**: Pre-push hook caught all regressions before commit
3. **Self-Test Mode**: Every new tool has `--self-test` flag for validation
4. **Python 3.10+ Type Hints**: Modern syntax (dict[str, int] vs Dict) enforced consistently
5. **Conventional Commits**: All 12 commits follow feat/fix/docs/test format with Co-Authored-By trailer

---

## What Could Improve

1. **Test Coverage**: Still at ~85%, target is 100% for core modules
2. **OpenCode Timeout Handling**: Need better timeout prediction (task complexity → time estimate)
3. **Session Analytics UI**: CLI-only, could benefit from web dashboard
4. **Documentation**: Some tools lack comprehensive usage examples

---

## Next Steps (Optional - Week 5+)

### Architecture Layer (Low Priority)
- [ ] Task 5.1: Capability seam documentation
- [ ] Task 5.2: Agent scope system

### Continuous Improvement
- [ ] Raise test coverage to 100%
- [ ] Add more E2E test scenarios
- [ ] Performance optimization for gate suite
- [ ] Session analytics web dashboard

---

## References

- **Upgrade Plan**: `.solocode/upgrade-plan.md`
- **DeepSeek Harness**: `deepseek-harness-master/` (reference, not part of project)
- **Git History**: `git log --oneline --graph -15`
- **Verification Command**: `python .claude/hooks/pre_push.py` (runs all 6 gates)

---

**Generated**: 2026-08-14
**Pattern Source**: DeepSeek harness (226 packages, 2+ years production)
**Executor**: OpenCode CLI (DeepSeek V4 Pro via purchased quota)


---

## 3. Early system health audits

### Source: `docs/audit-2026-08-15.md`

> Moved here verbatim on 2026-10-16.

# Audit Report — 2026-08-15 (Post-DeepSeek Upgrade)

> **Người thực hiện:** Claude Code
> **Ngày:** 2026-08-15
> **Phạm vi:** Toàn bộ project sau khi DeepSeek thực hiện comprehensive upgrade (commit `89cdfd0` và 5 commit trước đó)

---

## Tóm tắt điều hành (Executive Summary)

**Kết luận:** Dự án trong trạng thái **xuất sắc** sau đợt nâng cấp của DeepSeek. Tất cả verification gates đều PASS, không phát hiện bug logic hoặc security issue.

**DeepSeek đã nâng cấp gì:**
- Hoàn thành tầng A1 của dsh-port-plan (bản đồ 49 package + 8 bài học)
- Hoàn thành tầng A2 (subagent seam interface với `evidence`/`summary` separation)
- Hoàn thành tầng A3 (compaction budget policy + tool-result pruner)
- Nâng test coverage từ 49% → 55% (4 test file mới: agent_scope, session_persistence, snapshot_testing, validate_schemas)
- Thêm 452 unit tests (tăng từ ~384), tất cả PASS

**Vấn đề còn sót:** 0 bug nghiêm trọng. Chỉ có coverage gap ở 11 file utility/delegate (không ảnh hưởng production).

---

## 1. Verification Gates Status

Chạy tại `89cdfd0` (HEAD):

| Gate | Kết quả | Chi tiết |
|---|---|---|
| `pytest tools/ -q` | ✅ **PASS** | 452 passed, 3 skipped (E2E cần API key) |
| `ruff check .` | ✅ **PASS** | All checks passed |
| `check_lint_budget.py` | ✅ **PASS** | 57/57 (at budget) |
| `security_scan.py .` | ✅ **PASS** | 579 files, 0 issues |
| `checklist.py .` | ✅ **PASS** | 5/5 checks (Secret/Ruff/Boundary/Harness/Guard) |
| `validate_schemas.py` | ✅ **PASS** | 64 files, 0 errors |
| `garden.py` | ✅ **PASS** | 0 drift issues (fixed phantom file ref) |

**Evidence:**
```bash
$ python -m pytest tools/ -q --tb=no
452 passed, 3 skipped in 47.70s

$ ruff check .
All checks passed!

$ python tools/check_lint_budget.py
[OK] At budget.

$ python .github/scripts/security_scan.py .
No issues found.

$ python .github/scripts/checklist.py .
[PASS] All checks PASSED

$ python tools/validate_schemas.py
All schemas valid.

$ python tools/garden.py
Garden is clean — no drift detected.
```

---

## 2. Test Coverage Analysis

### 2.1 Tổng quan

| Metric | Giá trị |
|---|---|
| **Total coverage** | **55%** (6042 stmts, 2739 miss) |
| **Files tracked** | 41 production files |
| **Test files** | 18 files (100% của chúng đều có >97% coverage) |
| **Tests count** | 452 unit tests |

### 2.2 Files at 0% coverage (11 file)

**Không phải bug — tất cả đều có lý do chính đáng:**

| File | Lines | Lý do chấp nhận 0% |
|---|---|---|
| `compaction.py` | 44 | **Mới port tuần này** — đang chờ integration test với hook |
| `compaction_pruner.py` | 93 | **Mới port tuần này** — có `--self-test` riêng, chưa pytest formal |
| `subagent_seam.py` | 59 | **Mới port tuần này** — có `--self-test` riêng, chưa pytest formal |
| `coverage_gate.py` | 134 | **Infra tool** — chạy mỗi CI, không unit-test chính nó |
| `harness_config.py` | 197 | **Config parser** — chưa ưu tiên, không có bug report |
| `kilo_cli_delegate.py` | 109 | **Delegate wrapper** — integration-tested qua end-to-end |
| `opencode_delegate.py` | 110 | **Delegate wrapper** — integration-tested qua end-to-end |
| `kilo_server_manager.py` | 229 | **Server lifecycle** — tested manually, rare changes |
| `kilo_usage_report.py` | 54 | **Reporting tool** — chạy post-session, không critical path |
| `session_analytics.py` | 202 | **Analytics tool** — có `--self-test`, chưa pytest formal |
| `solocode_config.py` | 104 | **Config loader** — chưa ưu tiên, không có bug report |

**Khuyến nghị:** Không cần urgent action. 3 file mới port (compaction*, subagent_seam) đã có `--self-test` pass, sẽ bổ sung pytest khi có time budget.

### 2.3 Coverage cải thiện (8 files)

DeepSeek vừa nâng coverage cho 4 core module:

| File | Coverage | Cải thiện |
|---|---|---|
| `agent_scope.py` | 56% | **+55.6%** (từ 0%) |
| `session_persistence.py` | 43% | **+42.5%** (từ 0%) |
| `snapshot_testing.py` | 49% | **+49.1%** (từ 0%) |
| `validate_schemas.py` | 62% | (đã có baseline) |

---

## 3. Code Quality Analysis

### 3.1 Lint Status

- **Ruff select rules:** E, F, W, I, N, UP, B, SIM, C4
- **Ignored:** E501 (line-too-long) — 240 instances, design decision
- **Bandit/BLE budget:** 57/57 (at budget, không tăng)

**No violations** trong:
- Naming conventions (N)
- Python upgrades (UP)
- Bugbear patterns (B)
- Simplification opportunities (SIM)
- Comprehension issues (C4)

### 3.2 Code Smell Scan

**Tìm kiếm TODO/FIXME/XXX/HACK/BUG:**

```bash
$ grep -r "TODO\|FIXME\|XXX\|HACK\|BUG" tools/*.py .claude/hooks/*.py
tools/test_secret_patterns.py:    ("short_placeholder", 'api_key = "TODO"'),
```

**Kết quả:** 0 technical debt marker (chỉ có 1 test fixture hợp lệ).

---

## 4. Architecture & Design Review

### 4.1 DeepSeek Port Plan Progress

Theo `docs/dsh-port-plan.md` và `docs/dsh-port-map.md`:

| Tầng | Trạng thái | Deliverables |
|---|---|---|
| **A0** (debt fix) | ✅ **DONE** | session_persistence default-arg fix, coverage-budget.json created |
| **A1** (port map) | ✅ **DONE** | `dsh-port-map.md` (49 packages mapped, 8 lessons extracted) |
| **A2** (subagent) | ✅ **DONE** | `tools/subagent_seam.py` (interface, evidence/summary separation) |
| **A3** (compaction) | ✅ **DONE** | `tools/compaction.py` + `tools/compaction_pruner.py` |
| **B/C** (SDK/runtime) | ❌ **BLOCKED** | Missing DEEPSEEK_API_KEY, Node version too old |

**Nghiệm thu A1-A3:**
- [x] `--self-test` pass cho 3 tool mới
- [x] `pytest tools/ -q` xanh
- [x] `security_scan.py .` — 0 issue
- [x] `checklist.py .` pass
- [x] Không sửa harness file để fix project issue
- [x] Commit convention đúng

### 4.2 Harness Completeness

| Component | Claude | Kilo | Status |
|---|---|---|---|
| **Hooks** | 9 files | 21 files | ✅ Complete |
| **Skills** | 50 skills | 50 skills | ✅ Parity |
| **Agents** | 14 types | N/A | ✅ Working |
| **Commands** | 14 slash commands | N/A | ✅ Working |

### 4.3 Capability Seams Implemented

| Seam | Service Definition | Provider(s) | Consumer |
|---|---|---|---|
| Agent Scope | `agent_scope.py` | In-process registry | hooks, subagents |
| Session Persistence | `session_persistence.py` | SQLite WAL | session hooks |
| Subagent | `subagent_seam.py` | **1 provider** (OpenCode CLI) | orchestrator |
| Compaction | `compaction.py` | Budget policy + pruner | (pending hook wire) |
| Guard | `.claude/hooks/guard.py` | Regex patterns | PreToolUse |

**Quan sát:** Subagent seam có 1 provider duy nhất (OpenCode CLI) — đúng với nguyên tắc "don't split preemptively" từ dsh architecture note. Chỉ refactor khi provider thứ 2 xuất hiện.

---

## 5. Security Review

### 5.1 Secret Scan

**Phạm vi:** 579 files (excluding `.git`, `deepseek-harness-master`, cache dirs)

**Kết quả:** 0 secrets found

**Patterns checked:**
- API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
- AWS credentials
- Private keys (RSA, SSH)
- Generic secrets (password=, token=, etc.)

### 5.2 Destructive Command Protection

**Guard hook coverage:**
- ✅ `rm -rf /`, `rm -rf ~`, `rm -rf /tmp/`
- ✅ `git reset --hard`, `git push --force origin main`
- ✅ `DROP TABLE`, `dd if=/dev/zero`, `mkfs.ext4`
- ✅ `curl ... | bash`, PowerShell `Remove-Item -Recurse -Force`

**Test evidence:** 15/15 destructive patterns blocked (test_claude_guard.py)

### 5.3 SQL Injection / Command Injection

**Manual review of DB access:**

`session_persistence.py`:
```python
cursor.execute(
    "INSERT INTO sessions (...) VALUES (?, ?, ?, ?)",
    (session_id, branch, commit_sha, datetime.now().isoformat())
)
```
✅ **SAFE** — parameterized queries throughout, no string concatenation

`shared_state.py`:
```python
cursor.execute("SELECT value FROM kv WHERE key = ?", (key,))
```
✅ **SAFE** — parameterized queries

**Bash delegation:**
```python
# opencode_delegate.py
subprocess.run([opencode_bin, "run", ...], ...)
```
✅ **SAFE** — list-based subprocess, no shell=True

---

## 6. Documentation Review

| Doc | Status | Notes |
|---|---|---|
| `README.md` | ✅ Current | Mô tả đúng harness architecture |
| `CLAUDE.md` | ✅ Current | Auto-generated, sync với `.kilo/` |
| `AGENTS.md` | ✅ Current | Cross-engine rulebook |
| `docs/capability-seams.md` | ✅ **Fixed** | Phantom file refs đã được thay bằng `agent_scope.py` |
| `docs/dsh-port-plan.md` | ✅ Current | Kế hoạch đã chốt phạm vi A1-A3 |
| `docs/dsh-port-map.md` | ✅ Current | 49 packages mapped, 8 lessons linked |
| `docs/evaluation-report.md` | ✅ **Fixed** | Đã đánh dấu phantom file issue là resolved |
| `docs/upgrade-summary.md` | ⚠️ **Stale** | Line counts sai (ước lượng, không đo) — non-blocking |

**Garden drift:** 0 issues sau khi fix evaluation-report.md

---

## 7. Integration Points

### 7.1 Cross-Engine Session State

**Shared state DB:** `.solocode/sessions.db` (SQLite WAL mode)

**Engines accessing:**
- Claude Code (via `session_start.py` / `session_end.py`)
- Kilo Code (via `session-start.js` / `session-end.js`)
- Gemini/Antigravity (manual, via file-based handoff)

**Concurrency model:**
- WAL mode enables concurrent readers
- Single writer at session boundary (start/end)
- ✅ **No lock contention observed**

### 7.2 Executor Mode

**Current state:** `executor-mode` gate is **ON** (default fail-closed)

**Enforcement:**
- Claude: `.claude/hooks/guard.py` blocks Edit/Write/MultiEdit, delegates to `opencode_delegate.py`
- Kilo: `.kilo/hooks/pre-tool-use/executor-mode.js` same behavior

**Bypass paths:**
- `.gemini/antigravity/handoff/inbox/*` (delegation briefs)
- `.solocode/executor-mode` (toggle itself)

✅ **Working as designed** — OpenCode CLI confirmed as primary executor

### 7.3 MCP Servers

**Configured in `.mcp.json`:**
- context7 (library docs)
- ide (VS Code integration)
- memory (knowledge graph)
- playwright (browser automation)
- sequential-thinking (reasoning tool)
- tolaria (Obsidian vault)

✅ **All servers available** (announced by SessionStart hook)

---

## 8. Remaining Work (Non-Critical)

### 8.1 Test Coverage Gaps

**Ưu tiên thấp (không chặn release):**

1. `compaction.py` / `compaction_pruner.py` — có `--self-test`, cần pytest formal
2. `subagent_seam.py` — có `--self-test`, cần pytest formal
3. `session_analytics.py` — có `--self-test`, cần pytest formal
4. `kilo_cli_delegate.py` / `opencode_delegate.py` — integration-tested, cần unit test isolation

**Ước lượng:** 2-3 ngày để nâng coverage lên 65%

### 8.2 Documentation Accuracy

**`docs/upgrade-summary.md`:**
- Line count table (Week 1-4) sai (ước lượng chứ không đo từ `git show --stat`)
- **Khuyến nghị:** Chạy lại từ git history hoặc ghi rõ "estimated"

**Ảnh hưởng:** Low — không ảnh hưởng technical correctness

### 8.3 dsh-port-plan Tier B/C

**Đã chặn (không làm):**
- Thiếu `DEEPSEEK_API_KEY` riêng → không thể dùng dsh SDK
- Node `v22.12.0` < yêu cầu `^22.19 || >=24` → build fail

**Quyết định:** Chỉ làm tầng A (pattern mining) — đã hoàn thành 100%

---

## 9. Risk Assessment

| Risk Category | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Regression từ 0% coverage files | Low | Low | Tất cả có `--self-test` hoặc integration test |
| Secret leak | Low | Low | Guard hook + security_scan.py bắt 100% |
| Cross-engine drift | Low | Low | garden.py chạy mỗi commit, auto-detected |
| SQL injection | Low | Very Low | Parameterized queries throughout |
| Compaction pruner bug | Medium | Low | Có `--self-test` với multibyte/boundary cases |

**Overall risk level:** **LOW**

---

## 10. Khuyến nghị (Action Items)

### Bắt buộc (None)

Không có action item bắt buộc — dự án đã ở trạng thái xuất sắc.

### Tùy chọn (Optional, theo thứ tự ưu tiên)

1. **Bổ sung pytest cho 3 tool mới port** (compaction*, subagent_seam)
   - Effort: 0.5 ngày
   - Value: Nâng coverage lên 60%+

2. **Sửa line count trong upgrade-summary.md**
   - Effort: 0.25 ngày
   - Value: Documentation accuracy

3. **Wire compaction pruner vào hook**
   - Effort: 0.5 ngày
   - Value: Activate A3 deliverable trong production flow
   - Note: Cần chốt injection point (standalone tool vs PostToolUse hook)

4. **Nâng coverage cho delegate wrappers**
   - Effort: 1 ngày
   - Value: Coverage lên 65%+

---

## 11. Conclusion

**DeepSeek đã thực hiện comprehensive upgrade xuất sắc:**

✅ Tất cả verification gates PASS
✅ 0 security issues
✅ 0 logic bugs phát hiện
✅ Test coverage +6% (49% → 55%)
✅ Hoàn thành đúng 100% phạm vi dsh-port-plan tầng A
✅ Architecture patterns đúng theo capability seam + postmortem lessons
✅ Cross-engine parity maintained (garden.py clean)

**Dự án sẵn sàng cho production use.**

Coverage gaps còn lại đều ở utility/delegate layer (không critical path), và tất cả đều có fallback verification (`--self-test` hoặc integration test).

---

**Người kiểm tra:** Claude Code (Sonnet 5)
**Ngày:** 2026-08-15
**Commit:** `c8d743d` (post-audit, garden drift fixed)


### Source: `docs/audit-2026-09-04.md`

> Moved here verbatim on 2026-10-16.

# Audit & Health Report — 2026-09-04 (Final Verification)

> **Người thực hiện:** Gemini (Antigravity IDE)
> **Người giải quyết lỗi:** Claude Code (Orchestrator)
> **Thời điểm xác nhận:** 2026-09-04 17:02:00+07:00
> **Trạng thái:** 🟢 **ALL GATES PASSED (Dự án đạt 100% yêu cầu chất lượng)**

---

## Tóm tắt điều hành (Executive Summary)

Đợt kiểm tra và sửa lỗi toàn diện ngày 2026-09-04 đã **hoàn tất thành công xuất sắc**. Toàn bộ các vấn đề phát hiện ban đầu cũng như tác dụng phụ phát sinh đã được Claude Code phân tích gốc rễ chính xác và xử lý triệt để.

- **Toàn bộ 6 cổng verification gates đều PASS**.
- **Pytest test suite:** **452/452 passed**, 3 skipped (E2E yêu cầu live token).
- **Master Checklist:** **5/5 passed** (Secret, Ruff, Boundary, Harness, Guard).
- **Harness Drift:** **0 drift** trên cả 5 engine (`.kilo`, `.claude`, `.copilot`, `.gemini`, `.opencode`).

---

## 1. Kết quả kiểm tra Verification Gates (Độc lập xác minh)

| Gate | Lệnh thực thi | Kết quả | Chi tiết / Bằng chứng |
|---|---|---|---|
| **Master Checklist** | `python .github/scripts/checklist.py .` | 🟢 **PASS (5/5)** | Secret Scan (PASS), Ruff Linter (PASS), Boundary Audit (PASS), Harness Eval (PASS), Guard Hook Syntax (PASS). |
| **Unit & Integration Tests** | `python -m pytest tools/` | 🟢 **PASS** | **452 passed**, 3 skipped in 42.76s. |
| **Ruff Linter** | `ruff check .` | 🟢 **PASS** | All checks passed (0 errors, 0 warnings). |
| **Lint Budget Gate** | `python tools/check_lint_budget.py` | 🟢 **PASS** | 60/60 findings (At budget). |
| **Secret Scan** | `python .github/scripts/security_scan.py .` | 🟢 **PASS** | 593 files scanned, 0 issues found. |
| **Harness Garden Audit** | `python tools/garden.py` | 🟢 **PASS** | 0 drift issues across all engines. |

---

## 2. Tổng kết các vấn đề đã được khắc phục hoàn toàn

### 1. File mới `tools/benchmark_executors.py`:
- **Lỗi Lint `SIM118`:** Đã loại bỏ `.keys()` tại vòng lặp `for m in by_model`.
- **Lỗ hổng bảo mật `S602` (`shell=True`):** Đã chuyển sang sử dụng `shlex.split` và `shell=False`.
- **Lỗi `BLE001` (Blind Exception):** Đã bắt danh sách ngoại lệ cụ thể `(subprocess.SubprocessError, OSError, ValueError)`.
- **Lint Budget:** Đã giải trình hợp lý và tăng mức chặn trong `tools/config/lint-budget.json` lên 60 findings.

### 2. Pytest PermissionError & Garden Bug Exposure:
- **Cấu hình Pytest:** Đã thêm `addopts = "--basetemp=.pytest_temp"` vào `pyproject.toml` và ignore `.pytest_temp/` trong `.gitignore`, khắc phục lỗi phân quyền Windows `%TEMP%`.
- **Bug 1 trong `_doc_scan_skip_dirs()` ([tools/garden.py](file:///F:/Project/Solo-Code-CLI/tools/garden.py)):**
  Khi `git ls-files` trả về stdout rỗng (do thư mục bị gitignore), hàm nhận diện đây là non-git context và fallback về static set:
  ```python
  if not proc.stdout.strip():
      return skip
  ```
- **Bug 2 trong các hàm quét tài liệu (`check_doc_paths`, `check_doc_flags`, `check_enforcement_claims`):**
  Chuyển sang dùng relative path (`md.relative_to(root).parts`) thay vì absolute path để tránh việc tên thư mục tạm trùng lặp với `skip_dirs`.

---

## 3. Kết luận & Đề xuất tiếp theo

Dự án hiện đã ở trạng thái **sạch hoàn toàn, ổn định và sẵn sàng**:
1. Đã sẵn sàng để staging và tạo commit cho nhánh tính năng **OpenCode Engine v4.2.0 + Benchmark Executors**:
   - `git add .`
   - `git commit -m "feat(opencode): reintroduce opencode engine v4.2.0 and benchmark tools"`
2. OpenCode CLI trên máy đã được nâng cấp lên bản mới nhất `1.18.27`.


---

## 4. The DeepSeek upgrade cross-review dossier

### Source: `docs/deepseek-harness-upgrade-review-plan.md`

> Moved here verbatim on 2026-10-16.

# Yêu cầu DeepSeek phản biện kế hoạch nâng cấp Solo-Code-CLI

## Vai trò

Bạn là reviewer độc lập. Hãy kiểm tra kế hoạch đánh giá và nâng cấp harness của repository:

`F:\Project\project_tools\Solo-Code-CLI`

Mục tiêu là tìm những điểm còn thiếu, giả định sai, false positive, rủi ro triển khai và thử nghiệm cần bổ sung. Không chỉnh sửa file trong repository.

## Bối cảnh

Repository là Solo-Code Harness đa engine, hỗ trợ Kilo, Claude Code, OpenCode, Copilot, Gemini và Codex.

Các thành phần chính:

- `AGENTS.md`, `CLAUDE.md`, `.harness.lock`
- `.kilo/`, `.claude/`, `.copilot/`, `.gemini/`, `.opencode/`
- `.solocode/shared-state.db`
- `tools/shared_state.py`, `tools/garden.py`, `tools/generate_harness.py`
- `tools/validate_schemas.py`, `tools/subagent_seam.py`
- `.github/scripts/checklist.py`, `.github/scripts/security_scan.py`
- `init.sh`, `Makefile`

Nguồn tham khảo mới:

`learn-harness-engineering-main/`

Đây là tài liệu và công cụ tham khảo, chưa được xem là code production.

## Kết quả đã biết

Đã chạy:

```powershell
node learn-harness-engineering-main/skills/harness-creator/scripts/validate-harness.mjs --target . --json
```

Kết quả:

```text
overall: 52
bottleneck: state
```

Các finding chính:

- Không tìm thấy `feature_list.json`.
- Không tìm thấy `progress.md`.
- Không tìm thấy session handoff template.
- Không phát hiện rõ one-feature-at-a-time rule.
- Không phát hiện feature dependencies.
- Không phát hiện completion gate đầy đủ.

Repository hiện đã có SQLite feature state, `evidence`, `last_updated`, session log, memory tables, lifecycle hooks, `init.sh`, verification gates, security scan và garden/drift checks. Vì vậy điểm 52 có thể phản ánh giới hạn của validator generic thay vì chất lượng harness thật.

Audit script tham khảo là `learn-harness-engineering-main/tools/audit-harness.sh`. File này có 438 dòng, không phải 543 dòng như một phân tích trước đó đã nêu.

Template feature list của khóa học dùng `not-started`, `in-progress`, `blocked`, `done`. Solo-Code-CLI hiện dùng `not-started`, `in-progress`, `completed`, `blocked`.

## Kế hoạch cần được phản biện

### Giai đoạn 1: Khóa baseline

Chạy và lưu kết quả:

```powershell
git status --short
git branch --show-current
python .github/scripts/security_scan.py .
python .github/scripts/check_skips.py tools/
python .github/scripts/checklist.py .
python tools/validate_schemas.py
python tools/garden.py
python -m pytest tools/ -q
python tools/test_integration.py
.\init.sh
python tools/shared_state.py show
python tools/shared_state.py features
```

Chạy riêng các công cụ tham khảo:

```powershell
node learn-harness-engineering-main/skills/harness-creator/scripts/validate-harness.mjs --target . --json
```

Nếu có Git Bash:

```bash
bash learn-harness-engineering-main/tools/audit-harness.sh .
```

Không đưa audit generic vào gate chính ngay.

### Giai đoạn 2: Phân loại finding

Với mỗi finding, lập bảng:

| Finding | Công cụ | Cơ chế hiện có | Gap thật? | Hành động |
|---|---|---|---|---|

Một finding chỉ được xem là gap thật khi có lỗi tái hiện được bằng command/test, session thực tế bị mất trạng thái, verification gate cho pass sai, engine xử lý khác nhau do thiếu tài liệu, hoặc state tồn tại nhưng không thể khôi phục.

### Giai đoạn 3: Thử nghiệm

#### 3.1 State adapter

So sánh fixture dùng SQLite hiện tại với fixture dùng `feature_list.json`. Kiểm tra validator có thể đọc SQLite hay cần adapter. Không tạo `feature_list.json` production nếu việc đó tạo hai nguồn sự thật.

#### 3.2 Audit script

Đánh giá thời gian chạy, false positive, overlap với `checklist.py`, `garden.py`, `boundary_audit.py`, khả năng chạy trên PowerShell/Git Bash/CI và tác động của exit code. Ban đầu chỉ dùng audit dưới dạng report.

#### 3.3 Mutation test verification

Tạm thời làm hỏng test, lint và security scan; kiểm tra gate có fail-fast và trả exit code đúng không.

#### 3.4 Session restart

Mô phỏng session A đặt feature thành `in-progress`, ghi evidence/blocker/files/next step, rồi khởi động session B. Kiểm tra có khôi phục đủ trạng thái không. Chỉ thêm progress/handoff artifact nếu thử nghiệm chứng minh state hiện tại chưa đủ.

### Giai đoạn 4: Nâng cấp theo ưu tiên

#### P0 — Tài liệu và routing

- Mô tả SQLite là nguồn feature state chính.
- Mô tả `evidence` và `last_updated`.
- Ghi rõ startup, restart và verification workflow.
- Ghi rõ one-feature-at-a-time nếu đây là quy tắc thực sự được áp dụng.

#### P1 — State/lifecycle

Chỉ thực hiện nếu có gap thật: session handoff template, blocker/next-step fields, stale feature check, feature dependencies hoặc adapter để validator hiểu SQLite. Không thêm `testedAt` nếu `last_updated` đã đủ.

#### P2 — Audit integration

Chỉ tích hợp audit sau khi false positive được phân loại, có wrapper phù hợp với Windows, exit code được hiệu chỉnh và không tạo gate trùng hoặc mâu thuẫn.

#### P3 — Đo hiệu quả

Chạy 3–5 task đại diện trước và sau nâng cấp. Đo số lần mất context, báo hoàn thành khi gate chưa pass, sửa ngoài scope, thời gian khôi phục session, số lần người dùng phải nhắc lại context và false positive của audit.

## Câu hỏi cần DeepSeek trả lời

1. Kế hoạch còn thiếu subsystem, failure mode hoặc thử nghiệm nào không?
2. Có nên duy trì SQLite làm nguồn sự thật duy nhất không? Vì sao?
3. Có rủi ro nào khi thêm `feature_list.json`, `progress.md` hoặc `testedAt` không?
4. Validator generic nên sửa để hiểu SQLite, bọc bằng adapter hay chỉ xem là công cụ tham khảo?
5. Audit shell có phù hợp với Windows và kiến trúc đa engine không?
6. Có cần kiểm tra thêm generated-file drift, concurrent engine access, lock expiration, compaction/restart, stale feature, cross-engine parity, security boundary hoặc subagent evidence không?
7. Acceptance criteria hiện tại có đủ chặt không?
8. Có chỉ số nào khó đo hoặc dễ bị đánh giá sai không?
9. Thứ tự P0/P1/P2/P3 có tối ưu không?
10. Có đề xuất nào đang dựa trên giả định chưa được kiểm chứng không?

## Định dạng báo cáo bắt buộc

### 1. Executive review

- Đánh giá: `đủ / còn thiếu / cần điều chỉnh lớn`.
- Ba rủi ro lớn nhất.
- Một đề xuất cần thay đổi ngay.

### 2. Missing checks

| Mục còn thiếu | Vì sao quan trọng | Command/test đề xuất | Mức độ |
|---|---|---|---|

### 3. False-positive risks

| Công cụ/finding | Vì sao có thể sai | Cách xác minh |
|---|---|---|

### 4. Architecture review

Đánh giá riêng SQLite state, lifecycle hooks, generated engine files, locks/concurrency, evidence model, session restart và subagent seam.

### 5. Revised experiment plan

Mỗi bước phải có mục tiêu, input, command, output cần lưu, tiêu chí pass/fail và rủi ro.

### 6. Revised upgrade roadmap

Phân loại thành: phải làm, nên làm, chỉ làm khi có evidence và không nên làm.

### 7. Acceptance criteria

Đưa ra tiêu chí định lượng hoặc command cụ thể để xác nhận từng nâng cấp.

### 8. Uncertainty

Liệt kê mọi nhận định chưa thể kết luận nếu chưa đọc hoặc chạy file cụ thể.

## Ràng buộc

- Không tự động sửa file.
- Không copy nguyên trạng toàn bộ khóa học vào production.
- Không coi structural benchmark là bằng chứng harness vận hành tốt hoặc kém.
- Không gọi một field là bắt buộc nếu schema hoặc code hiện tại chưa yêu cầu.
- Không đưa ra số liệu benchmark nếu chưa chạy command tương ứng.
- Phân biệt rõ evidence quan sát được, suy luận, giả thuyết và đề xuất.
- Khi nêu kết luận, phải kèm file, command hoặc output làm bằng chứng.


### Source: `docs/deepseek-harness-upgrade-review-response.md`

> Moved here verbatim on 2026-10-16.

# Phản biện kế hoạch nâng cấp Solo-Code-CLI

> **Vai trò:** Reviewer phản biện (Kilo).
> **Đối tượng review:** [`deepseek-harness-upgrade-review-plan.md`](deepseek-harness-upgrade-review-plan.md).
> **Ngày:** 2026-09-26.
> **Phạm vi:** Chỉ phân tích và phản biện. Không sửa mã nguồn harness được review. File này là báo cáo trả lời, không phải thay đổi code.
> **Quy ước nhãn:** mỗi nhận định được gắn `[Bằng chứng]` (quan sát được, kèm command/output), `[Suy luận]`, `[Giả thuyết]` hoặc `[Đề xuất]`.

---

## 0. Phương pháp và bằng chứng nền

Các command đã chạy (Windows PowerShell 5.1, Node v22.23.2):

```text
git status --short ; git branch --show-current
node learn-harness-engineering-main/skills/harness-creator/scripts/validate-harness.mjs --target . --json
python tools/garden.py
python tools/validate_schemas.py
(Get-Content learn-harness-engineering-main/tools/audit-harness.sh | Measure-Object -Line).Lines
```

Kết quả thô:

- `[Bằng chứng]` Validator tái hiện **`overall=52, bottleneck=state`** — số liệu trong kế hoạch là đúng.
- `[Bằng chứng]` `audit-harness.sh` = **438 dòng** — khớp với đính chính trong kế hoạch.
- `[Bằng chứng]` `tools/garden.py` → exit 0, "Total drift issues: 0".
- `[Bằng chứng]` `tools/validate_schemas.py` → "Files checked: 66, Errors: 0".
- `[Bằng chứng]` `ruff 0.15.15` có trong PATH.
- `[Bằng chứng]` `git status --short` cho thấy `?? learn-harness-engineering-main/` và `?? docs/` đang untracked; nhánh `main`.

---

## 1. Executive review

**Đánh giá tổng thể: `cần điều chỉnh lớn`.**

Kế hoạch đúng về cấu trúc (4 giai đoạn, phân loại finding, không thần thánh hoá structural benchmark) và đúng về số liệu validator. Nhưng nó **thiếu nghiêm trọng ở đầu vào finding** và **sai ở tiền đề P0/P1**, nên nếu thực thi nguyên trạng sẽ dẫn tới hoặc tài liệu hoá một quy trình không chạy, hoặc tạo nguồn sự thật thứ hai.

**Ba rủi ro lớn nhất:**

1. **Tiền đề "SQLite là nguồn feature state chính" (P0) trái với tài liệu hiện hành của chính repo.** `[Bằng chứng]` `.opencode/instruction/shared-state.md` ghi bảng `features` = **0 rows, "Không ai — dùng git log + MEMORY.md thay thế"**, đồng thời ghi rõ một quy trình session "MANDATORY" 9 bước trước đây **đã bị gỡ vì 0/9 bước thực sự chạy**. `[Bằng chứng]` Ở chiều ngược lại, `AGENTS.md:179-181` lại ra lệnh "Pick exactly ONE `in-progress` feature … Do NOT work on multiple features in one session". **Hai tài liệu auto-loaded tự mâu thuẫn.** Kế hoạch không phát hiện mâu thuẫn này.

2. **Danh sách finding của kế hoạch thiếu 3/13 check thất bại, trong đó có một gap thật.** `[Bằng chứng]` Validator thực tế fail **13 check** (bảng đầy đủ ở mục 2), kế hoạch chỉ nêu 6. Hai check bị bỏ sót là false negative do khớp từ khoá; một check bị bỏ sót — **`Verification fails fast`** — là gap thật: `init.sh:14` chỉ có `set -u`, `verify.sh:3` cũng chỉ `set -u`, không có `set -e`.

3. **`learn-harness-engineering-main/` chưa được `.gitignore` loại trừ.** `[Bằng chứng]` `.gitignore` có mục "Reference checkouts of upstream projects … Never committed" liệt kê `deepseek-harness-master/`, `open-code-review-main/`, `antigravity-sdk-python-main/` — **thiếu** `learn-harness-engineering-main/` (2478 file, đang `??`). `[Suy luận]` Hiện `security_scan.py` tự loại nó nhờ `untracked_top_level_dirs()` (dòng 106-142), nhưng cơ chế đó chỉ đúng chừng nào thư mục còn untracked; một `git add -A` sẽ hút trọn nó vào history và vô hiệu hoá cơ chế loại trừ.

**Một đề xuất cần thay đổi ngay:** trước khi làm P0/P1, **chốt mô hình state** (SQLite-only hay file-based projection) và **thêm `learn-harness-engineering-main/` vào `.gitignore`**. Hai việc này rẻ, chặn rủi ro lớn, và quyết định toàn bộ hướng P0→P2.

---

## 2. Missing checks

`[Bằng chứng]` 13 check thất bại thực tế từ validator:

```text
FAIL instructions: Definition of done documented
FAIL instructions: State artifacts routed from instructions
FAIL state: Feature tracker exists
FAIL state: Feature tracker is valid and has feature fields
FAIL state: Progress log exists
FAIL state: Progress log supports restart
FAIL state: Handoff captures blockers/files/next step
FAIL verification: Verification fails fast
FAIL scope: One-feature-at-a-time rule exists
FAIL scope: Feature dependencies are tracked
FAIL scope: Completion gate limits scope closure
FAIL lifecycle: Session handoff template exists
FAIL lifecycle: Session restart markers exist
```

Kế hoạch bỏ sót 3 check: `Definition of done documented`, `State artifacts routed from instructions`, `Verification fails fast`.

| Mục còn thiếu | Vì sao quan trọng | Command/test đề xuất | Mức độ |
|---|---|---|---|
| Mâu thuẫn `AGENTS.md` ↔ `.opencode/instruction/shared-state.md` về feature state | Hai tài liệu auto-loaded mâu thuẫn; agent không biết tin cái nào; P0/P1 đang xây trên giả định sai | So khớp trực tiếp hai file; quyết định một nguồn | **Cao** |
| `Verification fails fast` (init.sh `set -e`) | Entrypoint bootstrap không fail-fast; gate có thể báo OK dù bước trước lỗi | `Select-String -Path init.sh -Pattern 'set -e'`; thêm dòng lỗi giả vào init.sh và xem exit | **Cao** |
| `learn-harness-engineering-main/` chưa ignore | `git add -A` hút 2478 file bên thứ ba; phá auto-exclude của security_scan; đúng failure mode 248 false positive đã có tiền lệ | `git check-ignore learn-harness-engineering-main/`; `git status --short` | **Cao** |
| Lock/concurrency cross-engine chưa có thí nghiệm | `AGENTS.md` nói lock là cơ chế chống ghi đè duy nhất giữa engine, nhưng Phase 3 không test | 2 tiến trình `acquire_lock` cùng path, khác engine → kỳ vọng cái thứ hai `False` | **Cao** |
| Lock expiration chưa test | `active_locks` có `expires_at` và `_expire_locks()` nhưng chưa có bằng chứng hết hạn đúng | Acquire với TTL ngắn, chờ quá hạn, `get_active_locks()` → kỳ vọng rỗng | Trung bình |
| Generator idempotency + garden re-run | P3 nói "generated drift" nhưng không có bước regenerate-rồi-diff | `python tools/generate_harness.py --harness all` rồi `python tools/garden.py` → kỳ vọng drifts=0 và `git diff` rỗng | Trung bình |
| Deploy-target validation | Sản phẩm của harness là deploy sang project đích; điểm 52 của repo này không đại diện target | `python tools/deploy.py deploy <tmp>` rồi chạy validator/garden trên target | **Cao** |
| `checklist.py` bỏ qua tool thiếu | `FileNotFoundError` → `passed=True, skipped=True`; gate có thể PASS khi thiếu `ruff` | `checklist.py` trên PATH không có ruff → soi dòng "Ruff Linter" | **Cao** |
| Cross-engine parity (OpenCode/Codex) | Kế hoạch nêu OpenCode và Codex nhưng Phase 3 không kiểm tra rulebook mirror | Chạy `opencode` / `codex` hook test; đối chiếu `.claude/` ↔ `.opencode/` | Trung bình |
| Subagent seam chưa được enforce | `SubagentResult` tách evidence/summary nhưng chưa có provider nào implement Protocol | Đọc `tools/subagent_seam.py`; kiểm tra `opencode_delegate` có trả evidence không | Trung bình |
| Session restart thực (đã liệt kê 3.4) | Cần thiết, nhưng phải chạy thật chứ không mô tả | Kịch bản A→B như kế hoạch, lưu output 2 phiên | Trung bình |

---

## 3. False-positive risks

| Công cụ/finding | Vì sao có thể sai | Cách xác minh |
|---|---|---|
| Validator `One-feature-at-a-time rule exists` | `[Bằng chứng]` `harness-utils.mjs:252` chỉ khớp literal `'One feature at a time'` / `'one-feature-at-a-time'`. `AGENTS.md:179-181` có quy tắc nhưng diễn đạt khác ("Pick exactly ONE … Do NOT work on multiple features"). → **False negative.** | Đọc `harness-utils.mjs:252`; so `AGENTS.md:179-181` |
| Validator `Definition of done documented` / `Completion gate limits scope closure` | `[Bằng chứng]` `:233` cần literal `'Definition of Done'` hoặc `'done only when'` trong dòng có cấu trúc. `AGENTS.md:375` có "Verification Gates / Before marking any task complete, verify:" — cùng ý, khác chữ. → **False negative.** | Đọc `harness-utils.mjs:233,256` |
| Validator `state` subsystem | `[Bằng chứng]` `loadHarnessFiles()` (`:336-354`) chỉ đọc **7 tên file ở thư mục gốc**; không có cơ chế adapter/plugin. SQLite không bao giờ được đọc. → "gap" ở đây là **giới hạn của công cụ**, không phải thiếu sót của harness. | Đọc `harness-utils.mjs:336-354`; thử đặt `feature_list.json` giả ở gốc rồi chạy lại |
| Validator `state` floor | `[Bằng chứng]` `score = Math.max(1, round(passed/total*5))` (`:269`) — subsystem 0/5 vẫn được 1 điểm. → Không phản ánh "một phần năm năng lực". | Đọc `harness-utils.mjs:269` |
| `audit-harness.sh` (công cụ tham khảo) | `[Suy luận]` Là shell generic, bash-only, không biết mô hình đa engine/`.kilo/` là source of truth. Nếu đưa vào gate sẽ tạo finding trùng với `garden.py`/`boundary_audit.py` và fail trên PowerShell. | `bash audit-harness.sh .` trên Git Bash; đối chiếu finding với `garden.py` |
| `checklist.py` Ruff check | `[Bằng chứng]` `checklist.py:95-97` bắt `FileNotFoundError` → coi như PASS. Máy thiếu `ruff` báo gate xanh. | Tạm ẩn ruff khỏi PATH rồi chạy `checklist.py` |
| `security_scan.py` trên reference repos | `[Bằng chứng]` Cơ chế loại trừ dựa trên "thư mục 0 file tracked" (`:106-142`). `[Suy luận]` Nếu reference repo được commit, cơ chế hết hiệu lực → quét 2478 file bên thứ ba → nhiễu. Docstring `:114` ghi tiền lệ "pushed the gate to 248 false positives". | `git add -A` trên bản nháp rồi chạy scan; hoặc thêm ignore rồi xác nhận |

---

## 4. Architecture review

### 4.1 SQLite state
`[Bằng chứng]` `tools/shared_state.py:102-156` có đủ bảng `features`, `session_log`, `active_locks`, `shared_memory_*`. `VALID_STATUSES` (`:42`) = `not-started/in-progress/completed/blocked`.
`[Bằng chứng]` `.opencode/instruction/shared-state.md` ghi `features` = 0 rows, `shared_memory_*` = 0 rows, chỉ `session_log` có dữ liệu (do hook tự ghi).
`[Suy luận]` Kết luận rủi ro số 1: SQLite mạnh về hạ tầng nhưng **feature state chưa từng hoạt động**. Trước khi tuyên bố nó là "nguồn sự thật chính", cần quyết định giữ hay gỡ; nếu giữ phải có cơ chế ghi thật sự (hook/CLI bắt buộc), nếu không thì rủi ro là tài liệu hoá điều không tồn tại — đúng điều mà `shared-state.md` vừa gỡ.

### 4.2 Lifecycle hooks
`[Bằng chứng]` Hook tự động ghi `session_log` cho Claude Code (`.claude/hooks/session_start.py`, `session_end.py`, `pre_compact.py`). Kilo có `.kilo/hooks/...`; Codex/OpenCode không có hook lifecycle tương đương trong mô tả.
`[Suy luận]` Đây là **điểm parity lệch giữa các engine**: cùng một repo nhưng Claude Code có observability tự động còn engine khác phải gọi tay. Kế hoạch Q6 hỏi "cross-engine parity" nhưng Phase 3 không có bước kiểm tra.

### 4.3 Generated engine files
`[Bằng chứng]` `tools/generate_harness.py` lấy `.kilo/` làm source of truth, sinh `.claude/`, `.opencode/`, và mirror sang `.copilot/`, `.gemini/antigravity/`. `tools/garden.py` kiểm tra parity `.kilo/ ↔ .copilot/` và drift `.claude/`.
`[Bằng chứng]` `garden.py` hiện sạch (drift = 0); `validate_schemas.py` 0 lỗi.
`[Đề xuất]` Vì `.kilo/` là nguồn cho instructions/skills, còn task state nằm nơi khác, tài liệu P0 phải phân biệt rõ **3 tầng nguồn sự thật**: (1) `.kilo/` cho instruction/skill/agent, (2) git log + `MEMORY.md` cho lịch sử/decision, (3) SQLite cho session/lock. Validator đang nhắm tầng thứ tư (`feature_list.json`), nên đừng trộn ba tầng kia vào lập luận.

### 4.4 Locks / concurrency
`[Bằng chứng]` `shared_state.py` dùng WAL + `BEGIN IMMEDIATE` (`_ImmediateTransaction`), có retry khi khởi tạo DB đồng thời (`_INIT_RETRY_ATTEMPTS = 10`, comment ghi đã tái hiện bug), lock có `expires_at`, hỗ trợ directory lock và release theo `session_id`.
`[Suy luận]` Hạ tầng lock **mạnh hơn mức kế hoạch giả định** (kế hoạch coi như cần làm P1/P2). Việc còn thiếu là **bằng chứng vận hành**, không phải code. Điều này củng cố đề xuất: chuyển lock từ "P1 phải làm" sang "thí nghiệm bắt buộc".

### 4.5 Evidence model
`[Bằng chứng]` `tools/subagent_seam.py:59-88` tách `evidence` (facts máy kiểm được) khỏi `summary` (prose không tin), kèm `stop_reason` union kín.
`[Suy luận]` Đây là contract đúng hướng. Nhưng `:24-27` ghi rõ provider hiện tại (`tools/opencode_delegate.py`) **chưa** implement Protocol; seam chỉ là Service Definition. Nghĩa là **chưa có enforcement**: không gì bắt consumer re-run evidence. Kế hoạch nên thêm bước kiểm chứng "delegate → đối chiếu evidence với `git status`/`git diff`".

### 4.6 Session restart
`[Bằng chứng]` `session_log` lưu `summary`, `features_touched`, `files_changed`, `commits`, `verification`.
`[Suy luận]` Mô hình hiện tại khôi phục được "phiên trước làm gì", nhưng **không khôi phục được "việc dở dang / blocker / next step"** — validator chỉ ra đúng: `Handoff captures blockers/files/next step` fail. Đây là gap thật có thể bảo vệ được bằng thí nghiệm A→B.

### 4.7 Subagent seam
`[Bằng chứng]` `subagent_seam.py` có `SubagentRequest`/`SubagentResult`/`SubagentRuntime` và `--self-test` pass logic (assert nội bộ).
`[Suy luận]` Seam đúng pattern nhưng chưa có provider thứ hai; theo `docs/dsh-port-plan.md` A2, chỉ refactor khi có provider thứ hai. Kế hoạch không nên đụng vào đây ở P0/P1.

---

## 5. Revised experiment plan

Mỗi bước: mục tiêu, input, command, output cần lưu, tiêu chí pass/fail, rủi ro.

| ID | Mục tiêu | Input | Command | Output lưu | Pass/Fail | Rủi ro |
|---|---|---|---|---|---|---|
| E0 | Khóa baseline + xác nhận 13 finding | repo sạch | `git status --short`; `python .github/scripts/security_scan.py .`; `python tools/garden.py`; `python tools/validate_schemas.py`; `python -m pytest tools/ -q` | `docs/review-artifacts/e0-baseline.txt` | Tất cả exit 0, trừ validator | pytest có thể >120s |
| E1 | Kiểm chứng validator root-only | copy `feature_list.json` mẫu vào gốc rồi xoá | `node ...validate-harness.mjs --target . --json` (2 lần) | before/after JSON | Điểm `state` đổi → xác nhận root-only | Vô tình commit file mẫu |
| E2 | Phân loại 13 finding | output E0 | Lập bảng Finding×Gap thật? | `e2-triage.md` | Mỗi finding gắn nhãn `thật`/`false-negative`/`giới hạn công cụ` | Trộn 3 loại |
| E3 | Fail-fast | bản sao `init.sh` | chèn lệnh `false` vào bản sao, chạy, soi exit | log exit code | Không `set -e` → các bước sau vẫn chạy | Sửa nhầm file gốc |
| E4 | Lock cross-engine | 2 tiến trình | `acquire_lock` cùng path, engine khác nhau | log `True/False` | Cái thứ hai phải `False` | SQLite busy |
| E5 | Lock expiration | TTL ngắn | acquire → sleep > TTL → `get_active_locks()` | output JSON | Danh sách rỗng | Đồng hồ hệ thống lệch |
| E6 | Generator idempotency | repo sạch | `python tools/generate_harness.py --harness all`; `python tools/garden.py`; `git diff --stat` | log + diff | drift=0, diff rỗng | Generator ghi file do môi trường |
| E7 | Session restart A→B | 2 phiên | A ghi summary/blocker/next; B đọc | transcript 2 phiên | B khôi phục được blocker+next | Cần thao tác thủ công |
| E8 | Gate skip tool | PATH thiếu `ruff` | chạy `checklist.py` | log 2 lần | Ghi nhận PASS-giả | Ẩnh hưởng PATH máy |
| E9 | Deploy target | thư mục tạm | `python tools/deploy.py deploy <tmp>`; chạy validator/garden trên target | log target | Target dùng được | Ghi ngoài workspace |

---

## 6. Revised upgrade roadmap

### Phải làm (chặn rủi ro, không phụ thuộc evidence)
- Giải quyết mâu thuẫn `AGENTS.md:179-181` ↔ `.opencode/instruction/shared-state.md`; chốt một quy tắc state. **Quyết định này phải ghi vào `.kilo/memory/MEMORY.md` `## Decisions`.**
- Thêm `learn-harness-engineering-main/` vào `.gitignore` (mục "Reference checkouts").
- Sửa baseline kế hoạch: `.\init.sh` → `bash ./init.sh` (có điều kiện Git Bash) hoặc thay bằng `python tools/shared_state.py show`.

### Nên làm (khi evidence xác nhận)
- Bổ sung "Definition of Done" theo đúng literal validator nếu muốn điểm phản ánh thật — hoặc ghi nhận đây là false negative.
- Thêm `set -e` (hoặc kiểm soát lỗi tương đương) vào `init.sh` nếu chấp nhận fail-fast.
- Thí nghiệm lock/concurrency + expiration (E4, E5).
- Thí nghiệm deploy target (E9).

### Chỉ làm khi có evidence
- Bổ sung `session-handoff` / blocker-next-step: chỉ sau khi E7 chứng minh `session_log` không đủ.
- `progress.md` / `feature_list.json`: chỉ nếu chấp nhận projection một chiều từ SQLite, và phải ghi rõ chống hai nguồn sự thật.
- Tích hợp `audit-harness.sh`: chỉ sau khi phân loại false positive và có wrapper Windows.
- Adapter SQLite cho validator: **không khả thi** về mặt kỹ thuật (xem 4.3 / mục 7), nên đây cũng thuộc nhóm "không nên làm".

### Không nên làm
- Không thêm `feature_list.json` ở gốc như nguồn sự thật thứ hai.
- Không đưa `audit-harness.sh` vào gate chính.
- Không copy nguyên khóa học vào production.
- Không thêm `testedAt` khi `last_updated` đã đủ (đồng ý với kế hoạch).
- Không refactor `subagent_seam.py` khi chưa có provider thứ hai.

---

## 7. Acceptance criteria

| Nâng cấp | Tiêu chí xác nhận (command) |
|---|---|
| Chốt state | `Select-String AGENTS.md, .opencode/instruction/shared-state.md` không còn mô tả trái nhau về feature workflow |
| Ignore reference dir | `git check-ignore learn-harness-engineering-main/` trả về đường dẫn (exit 0); `git status --short` không còn `?? learn-harness-engineering-main/` |
| Fail-fast | `init.sh` chứa `set -e`; bản sao có lệnh lỗi → exit != 0 |
| Lock cross-engine | E4: lock thứ hai trả `False`; `python tools/shared_state.py locks` chỉ 1 chủ |
| Lock expiration | E5: sau TTL, `python tools/shared_state.py locks` rỗng |
| Generator idempotency | `generate_harness.py --harness all` rồi `garden.py` → "Total drift issues: 0"; `git diff --stat` rỗng |
| Session restart | E7: phiên B in ra được blocker + next step + files của A mà không hỏi lại |
| Gate fail-fast | Mutation test (trên nhánh tạm) làm hỏng test/lint/security → `checklist.py` exit 1, có và không có `ruff` |
| Deploy target | E9: validator/garden trên target chạy được, không crash |
| Validator (nếu theo đuổi điểm) | `node ...validate-harness.mjs --target . --json` → `overall >= 70` **hoặc** có văn bản chấp nhận 52 là giới hạn công cụ generic |

---

## 8. Uncertainty

Các điểm **chưa thể kết luận** nếu chưa đọc/chạy cụ thể:

- `[Chưa chạy]` Toàn bộ `python -m pytest tools/ -q` và `python .github/scripts/checklist.py .` (chỉ mới chạy garden/validate_schemas/validator). Số test pass/fail chưa xác nhận.
- `[Chưa chạy]` `python tools/test_integration.py`, `python .github/scripts/check_skips.py tools/`, `python .github/scripts/security_scan.py .` end-to-end.
- `[Chưa chạy]` `audit-harness.sh` (cần Git Bash) — chưa đo thời gian chạy, false positive, exit code.
- `[Chưa kiểm chứng]` Hành vi `deploy.py` sang target và parity sau deploy.
- `[Chưa kiểm chứng]` Test Codex/OpenCode hook thực tế; chỉ suy từ cấu trúc file.
- `[Giả thuyết]` Việc `features` = 0 rows dựa trên tài liệu `shared-state.md`, chưa query trực tiếp `.solocode/shared-state.db` trong phiên này. Khuyến nghị chạy `python tools/shared_state.py features` để xác nhận số dòng.
- `[Chưa đọc hết]` `tools/generate_harness.py` (~dài) và `tools/garden.py` chỉ đọc phần đầu; kết luận parity dựa trên output chạy, không dựa trên đọc toàn bộ logic.
- `[Không xác định]` `score` của validator trên project đích sau deploy (validator chạy trên cây target chứ không phải cây nguồn).

---

## Phụ lục A — Ba dòng cần sửa/tìm trong code (để đối chiếu)

```text
learn-harness-engineering-main/skills/harness-creator/scripts/lib/harness-utils.mjs:233,252,256  # keyword matching
learn-harness-engineering-main/skills/harness-creator/scripts/lib/harness-utils.mjs:336-354      # root-only file load
.github/scripts/checklist.py:95-97                                                              # FileNotFoundError => pass+skip
.github/scripts/security_scan.py:106-142, 145-156                                               # untracked-top-level auto-exclude
tools/shared_state.py:42; 102-156; 218-221; 360-414                                              # statuses, schema, locks
init.sh:14 ; verify.sh:3                                                                          # set -u (thiếu set -e)
AGENTS.md:179-181 ; .opencode/instruction/shared-state.md                                         # mâu thuẫn feature state
.gitignore                                                                                        # thiếu learn-harness-engineering-main/
```


### Source: `docs/deepseek-harness-upgrade-review-followup.md`

> Moved here verbatim on 2026-10-16.

# Phản hồi vòng hai và yêu cầu DeepSeek xác nhận kế hoạch

## Đánh giá phản hồi trước

Phản hồi trước đã tìm thấy một mâu thuẫn kiến trúc quan trọng và có chất lượng tốt hơn phân tích ban đầu. Đặc biệt, các điểm sau đã được xác nhận là đáng điều tra:

1. `AGENTS.md` yêu cầu dùng `state.set_feature_status(...)`, trong khi `.opencode/instruction/shared-state.md` nói bảng `features` hiện không được dùng và quy trình thực tế dựa vào git log cùng `MEMORY.md`.
2. Validator generic không đọc SQLite, nên điểm `overall=52` không đủ để kết luận chất lượng harness.
3. `checklist.py` có thể coi tool bị thiếu là `passed=True, skipped=True`.
4. Lock, lock expiration, session restart và deploy target chưa có đủ bằng chứng vận hành.
5. `learn-harness-engineering-main/` đang untracked và chưa có entry tương ứng trong `.gitignore`.

Tuy nhiên, một số kết luận cần được hiệu chỉnh trước khi biến thành thay đổi code.

## Dữ liệu cần cập nhật

Tài liệu `.opencode/instruction/shared-state.md` chứa số liệu cũ. Query trực tiếp hiện tại cho kết quả:

```text
Features: 0
Sessions: 1000
Active locks: 1
```

Lock hiện tại nằm trong thư mục test tạm:

```text
f:/project/project_tools/solo-code-cli/.pytest_temp/test_write_benign_content_crea0/subdir/test_out.txt
locked by codex (codex-cli)
```

Vì vậy, hãy phân biệt:

- số liệu được ghi trong tài liệu cũ;
- số liệu runtime lấy trực tiếp từ SQLite;
- kết luận về thiết kế mong muốn.

Không dùng số liệu `active_locks=0` hoặc `session_log=350` trong tài liệu cũ làm bằng chứng hiện trạng.

## Quyết định kiến trúc cần xác nhận

Hãy đánh giá lại hai phương án sau.

### Phương án A: SQLite là nguồn feature state chính

Nếu chọn phương án này, kế hoạch phải bao gồm:

- cập nhật `.opencode/instruction/shared-state.md`;
- xác định engine hoặc hook nào ghi `set_feature_status()`;
- bảo đảm mọi engine có thể đọc cùng feature state;
- test trạng thái `in-progress`, `completed`, `blocked`;
- test session restart với feature, evidence, blocker và next step;
- tài liệu hóa cách khôi phục khi DB bị hỏng.

### Phương án B: SQLite chỉ lưu session và lock

Nếu chọn phương án này, kế hoạch phải bao gồm:

- bỏ quy tắc bắt buộc `set_feature_status()` khỏi `AGENTS.md`;
- ghi rõ feature tracking dùng git log và `MEMORY.md`;
- không mô tả SQLite là feature tracker chính;
- điều chỉnh validator findings để không coi thiếu `feature_list.json` là lỗi.

Không chấp nhận trạng thái tài liệu tiếp tục mô tả cả hai phương án cùng lúc.

## Các điểm cần sửa trong roadmap trước

### 1. `.gitignore`

Đề xuất thêm chính xác:

```gitignore
learn-harness-engineering-main/
```

Không ignore toàn bộ `docs/`, vì các file kế hoạch và phản hồi cần được giữ lại.

Hãy nêu rõ đây là thay đổi metadata/repository hygiene, không phải nâng cấp harness runtime.

### 2. Fail-fast

Không thêm `set -e` mù quáng vào mọi shell script.

- `init.sh` có thể cần fail-fast, nhưng phải chạy mutation test trước.
- `verify.sh` hiện có vẻ là aggregate reporter, cố tình thu thập nhiều lỗi trước khi kết thúc. Thêm `set -e` có thể làm mất báo cáo tổng hợp.
- `checklist.py` cần phân biệt tool bắt buộc và tool tùy chọn. `FileNotFoundError` không nên mặc định thành pass cho tool bắt buộc.

Hãy tách ba khái niệm:

1. fail-fast;
2. aggregate reporting;
3. optional skip.

### 3. Temporary fixture

Thí nghiệm validator không được tạo file trong root rồi xóa. Dùng thư mục tạm bên ngoài repository. Ví dụ:

```powershell
$temp = Join-Path $env:TEMP "solo-code-validator-fixture"
```

Nếu cần dọn thư mục tạm, phải xác nhận đường dẫn tuyệt đối trước khi xóa.

### 4. Generator test

`generate_harness.py --harness all` có thể sửa các file generated. Hãy yêu cầu:

- ghi nhận `git status` trước;
- chạy trên worktree sạch hoặc bản sao tạm;
- kiểm tra `git diff` sau khi chạy;
- không coi thay đổi generated là vô hại nếu chưa xác định nguyên nhân.

### 5. SQLite adapter

Không kết luận adapter SQLite là “không khả thi”. Kết luận chính xác hơn là:

> Adapter SQLite khả thi về kỹ thuật, nhưng chỉ đáng làm nếu validator trở thành công cụ chính thức của Solo-Code-CLI. Nếu validator chỉ là công cụ tham khảo, phân loại false positive sẽ ít rủi ro hơn.

## Thí nghiệm bắt buộc cần bổ sung

### E0 — Baseline đầy đủ

Chạy và lưu output của:

```powershell
python .github/scripts/security_scan.py .
python .github/scripts/check_skips.py tools/
python .github/scripts/checklist.py .
python tools/validate_schemas.py
python tools/garden.py
python -m pytest tools/ -q
python tools/test_integration.py
python tools/shared_state.py show
python tools/shared_state.py features
python tools/shared_state.py locks
python tools/shared_state.py sessions --limit 3
```

Kế hoạch phải ghi rõ command nào đã chạy thật và command nào chỉ mới được đề xuất.

### E1 — State contradiction

Đối chiếu trực tiếp:

- `AGENTS.md`
- `.opencode/instruction/shared-state.md`
- `tools/shared_state.py`
- `.claude/hooks/session_start.py`
- `.claude/hooks/session_end.py`

Output cần trả lời:

- feature state hiện được ghi ở đâu;
- engine nào ghi nó;
- engine nào chỉ đọc;
- quy trình nào đang được thực thi thật;
- quy trình nào chỉ tồn tại trong tài liệu.

### E2 — Lock cleanup

Điều tra active lock hiện tại trong `.pytest_temp`:

- test nào tạo lock;
- fixture có release lock không;
- lock có expiry không;
- test thất bại có để lại lock không.

Không xóa DB hoặc lock hiện tại trong quá trình điều tra nếu chưa có backup và xác nhận đường dẫn.

### E3 — Cross-engine lifecycle matrix

Lập bảng cho Kilo, Claude, OpenCode, Copilot, Gemini và Codex:

| Engine | Session start | Session end | Pre-compact | Shared state | Verification |
|---|---|---|---|---|---|

Mỗi ô phải có file hoặc command làm bằng chứng.

### E4 — Gate behavior

Kiểm tra riêng:

- tool bắt buộc bị thiếu;
- tool tùy chọn bị thiếu;
- test thất bại;
- lint thất bại;
- security scan thất bại.

Mỗi trường hợp phải ghi exit code và xem có báo `PASS` sai không.

### E5 — Session restart

Mô phỏng session A và B, nhưng phải kiểm tra cả hai phương án state:

- SQLite feature state;
- git log + `MEMORY.md`.

Không kết luận cần `progress.md` hoặc session handoff cho đến khi có output chứng minh blocker/next step thực sự bị mất.

## Phân loại đề xuất sau khi kiểm chứng

Hãy phân loại mỗi đề xuất vào đúng một nhóm:

### Phải làm

Chỉ dành cho lỗi đã tái hiện hoặc mâu thuẫn có thể khiến engine hành xử khác nhau.

### Nên làm

Giúp vận hành tốt hơn nhưng chưa chặn correctness.

### Chỉ làm khi có evidence

Ví dụ: `progress.md`, `session-handoff.md`, SQLite adapter, audit integration.

### Không nên làm

Ví dụ: thêm `feature_list.json` làm nguồn sự thật thứ hai, thêm `testedAt` không có use case, copy toàn bộ khóa học vào production.

## Acceptance criteria cần hiệu chỉnh

Không dùng `overall >= 70` làm acceptance criterion duy nhất. Có thể dùng score này như chỉ số phụ, nhưng acceptance phải dựa trên behavior.

Acceptance tối thiểu nên gồm:

- không còn mâu thuẫn state giữa các instruction file;
- không còn reference checkout untracked ngoài ý muốn;
- tool bắt buộc bị thiếu làm gate fail;
- lock cạnh tranh và expiry hoạt động đúng;
- session mới khôi phục được blocker và next step;
- generator không tạo drift ngoài dự kiến;
- toàn bộ security, schema, garden và test gates pass;
- có command tái hiện cho mỗi gap đã sửa.

## Yêu cầu DeepSeek trả lời vòng tiếp theo

Hãy trả lời theo cấu trúc:

### 1. Revised verdict

Kế hoạch sau phản hồi này là `đủ`, `còn thiếu` hay `cần điều chỉnh lớn`?

### 2. State decision

Chọn Phương án A hoặc B ở trên. Giải thích trade-off và nêu các file phải cập nhật.

### 3. Corrected experiment order

Đưa ra thứ tự E0–E5 sau khi loại bỏ các bước trùng hoặc nguy hiểm.

### 4. Required changes

Liệt kê file, thay đổi tối thiểu và acceptance command. Không viết patch.

### 5. Deferred changes

Liệt kê những đề xuất cần hoãn vì chưa có evidence.

### 6. Remaining omissions

Tìm thêm các gap chưa được nêu trong hai vòng review.

### 7. Confidence and uncertainty

Mỗi kết luận phải gắn một trong các nhãn:

- `[Evidence]`
- `[Inference]`
- `[Hypothesis]`
- `[Recommendation]`
- `[Not verified]`

## Ràng buộc

- Không sửa file trong repository.
- Không chạy lệnh xóa, reset hoặc thay đổi destructive.
- Không dùng số liệu trong tài liệu cũ thay cho query runtime.
- Không gọi structural benchmark là bằng chứng runtime behavior.
- Không tạo nguồn feature state thứ hai.
- Không đưa audit generic vào gate chính trước khi phân loại false positive.
- Không đề xuất thêm dependency mới.
- Mọi tuyên bố phải kèm file, command hoặc output làm bằng chứng.

---

# Kế hoạch chốt để thống nhất trước khi triển khai

## Quyết định state

Chọn **Phương án B**: feature tracking dùng git log và `.kilo/memory/MEMORY.md`; SQLite giữ session log, lock và cơ chế cộng tác phù hợp. Bảng `features` không phải nguồn feature state đang hoạt động. Không thêm `feature_list.json` hoặc `testedAt` làm nguồn sự thật thứ hai.

Lý do: quyết định này đã được ghi trong `.kilo/memory/decisions-archive.md`, runtime hiện có `Features: 0`, và không có hook/engine thực tế nào gọi `set_feature_status()`.

`AGENTS.md` và các instruction generated phải mô tả cùng workflow. `.kilo/` là nguồn cho instruction/skill/generated harness; git log và `MEMORY.md` là nguồn feature/task history; SQLite là runtime infrastructure. Không mặc định hợp nhất mọi bảng session trước khi lập bản đồ writer/reader.

## Thứ tự triển khai bắt buộc

### Bước 0 — Baseline

```powershell
git status --short
git branch --show-current
python .github/scripts/security_scan.py .
python .github/scripts/check_skips.py tools/
python .github/scripts/checklist.py .
python tools/validate_schemas.py
python tools/garden.py
python -m pytest tools/ -q
python tools/test_integration.py
python tools/shared_state.py show
python tools/shared_state.py features
python tools/shared_state.py locks
python tools/shared_state.py sessions --limit 3
```

Lưu output ở ngoài production state. Ghi rõ command nào pass, fail, skip hoặc chưa chạy. Không xóa DB, lock hoặc file test hiện tại.

### Bước 1 — Sửa mâu thuẫn feature state

Files dự kiến:

- `AGENTS.md`
- `.kilo/instruction/shared-state.md`
- `.kilo/memory/MEMORY.md` nếu cần ghi quyết định hiện hành

Thay đổi tối thiểu:

- bỏ yêu cầu bắt buộc gọi `state.set_feature_status()`;
- bỏ yêu cầu chọn SQLite feature `in-progress` nếu workflow thực tế không dùng bảng `features`;
- ghi rõ feature/task tracking dùng git log và `MEMORY.md`;
- cập nhật số liệu runtime cũ hoặc thay bằng command truy vấn;
- có thể giữ API `set_feature_status()` cho tương thích, nhưng phải ghi rõ API này không dùng trong workflow hiện tại.

Acceptance:

```powershell
rg -n "Pick exactly ONE|set_feature_status|features.*in-progress|git log|MEMORY.md" AGENTS.md .kilo/instruction/shared-state.md
python tools/generate_harness.py --harness all
python tools/garden.py
```

Không dùng tiêu chí máy móc “xóa mọi chuỗi `set_feature_status`”; tiêu chí là không còn yêu cầu dùng API đó trong workflow.

### Bước 2 — Lập bản đồ hai session store

Không hợp nhất ngay. Lập bảng bằng chứng:

| Store | Bảng | Writer | Reader | Hook/CLI | Dữ liệu duy nhất | Mục đích |
|---|---|---|---|---|---|---|
| `.solocode/shared-state.db` | `session_log` |  |  |  |  |  |
| `.solocode/sessions.db` | `sessions` |  |  |  |  |  |

Kiểm tra `tools/shared_state.py`, `tools/session_persistence.py`, `tools/session_analytics.py`, Claude hooks, Kilo hooks và Codex/OpenCode launchers. Chỉ quyết định giữ song song, hợp nhất hoặc deprecate sau khi biết đầy đủ consumer và dữ liệu không trùng.

### Bước 3 — Sửa lock lifecycle của Codex

`tools/codex_guard.py` hiện acquire lock nhưng không release sau thao tác ghi. Sửa theo hướng release trong `finally`, chỉ release lock do invocation/session sở hữu, và giữ fail-closed khi owner khác đang giữ lock.

Tests bắt buộc:

- ghi thành công rồi lock biến mất;
- ghi thất bại rồi lock biến mất;
- lock của engine khác vẫn chặn và không bị release nhầm;
- secret/destructive input bị chặn trước khi acquire lock.

```powershell
python -m pytest tools/test_codex_guard.py -q
python tools/shared_state.py locks
```

### Bước 4 — Sửa checklist khi thiếu tool

`checklist.py` phải phân biệt tool bắt buộc và tool tùy chọn. Tool bắt buộc bị thiếu phải fail với exit code khác 0; tool tùy chọn mới được skip. Output phải phân biệt `PASS`, `FAIL`, `SKIP`.

Mutation test phải bao phủ PATH không có `ruff`, test fail, lint fail và security scan fail.

### Bước 5 — Sửa drift docstring/tài liệu store

Kiểm tra `.claude/hooks/session_start.py` và tài liệu liên quan. Docstring phải khớp store code thực sự đọc. Tài liệu phải nêu vai trò riêng của `sessions.db` và `shared-state.db`, không tuyên bố một store là duy nhất trước khi Bước 2 có kết luận.

### Bước 6 — Ignore reference checkout

Thêm vào `.gitignore`:

```gitignore
learn-harness-engineering-main/
```

Đây là repository hygiene, không phải runtime upgrade. Xác nhận bằng:

```powershell
git check-ignore learn-harness-engineering-main/
git status --short
```

Không ignore toàn bộ `docs/`.

## Các việc hoãn

Chưa làm `feature_list.json`, `progress.md`, `session-handoff.md`, `testedAt`, SQLite adapter, audit integration, `set -e` cho `verify.sh`, refactor `subagent_seam.py` hoặc hợp nhất hai SQLite store nếu chưa có evidence riêng.

## Gate sau triển khai

```powershell
python .github/scripts/security_scan.py .
python .github/scripts/check_skips.py tools/
python .github/scripts/checklist.py .
python tools/validate_schemas.py
python tools/garden.py
python -m pytest tools/ -q
python tools/test_integration.py
```

Không dùng `overall >= 70` của validator generic làm acceptance criterion duy nhất.

## Yêu cầu DeepSeek xác nhận lần cuối

Hãy xác nhận hoặc phản biện sáu điểm sau trước khi triển khai:

1. Phương án B là quyết định đúng và không cần thêm `feature_list.json`.
2. Bước 0 phải chạy baseline đầy đủ trước khi sửa runtime.
3. Hai session store phải được lập bản đồ trước khi quyết định hợp nhất.
4. Lock trong `codex_guard.py` phải release trên success và exception, không release nhầm owner khác.
5. `checklist.py` phải fail khi thiếu tool bắt buộc và chỉ skip tool tùy chọn.
6. Các mục deferred không được triển khai chỉ để làm validator generic đạt điểm cao hơn.

Báo cáo xác nhận phải phân biệt `[Evidence]`, `[Inference]`, `[Recommendation]` và `[Not verified]`. Không sửa file trong bước xác nhận này.

---

# Xác nhận DeepSeek — đã thống nhất để triển khai

DeepSeek đã xác nhận cả sáu điểm của kế hoạch.

## Các điểm đã xác nhận

1. **Phương án B được giữ nguyên**: feature tracking dùng git log và `MEMORY.md`; không thêm `feature_list.json`.
2. **Baseline đầy đủ chạy trước runtime changes**; trạng thái từng command phải được ghi riêng.
3. **Hai session store giữ song song ở thời điểm hiện tại** vì khác schema, writer, reader và mục đích. Bước lập bản đồ phải bao gồm `tools/codex_session.py`.
4. **Codex phải release lock trên success và exception**, không release nhầm owner khác.
5. **Checklist phải fail khi thiếu tool bắt buộc**, đặc biệt là `ruff`; tool tùy chọn mới được skip.
6. **Không triển khai deferred items chỉ để tăng điểm validator generic**.

## Điều kiện bắt buộc cho Codex lock

Không được sửa đơn giản thành:

```python
state.release_lock(path, engine="codex")
```

`release_lock()` có thể xóa lock cùng engine khi không có `session_id`. Vì vậy implementation phải:

1. tạo `session_id` riêng cho mỗi invocation của `codex_guard.py`;
2. truyền cùng `session_id` vào `acquire_lock()`;
3. truyền chính `session_id` vào `release_lock()` trong `finally`;
4. không release nếu acquire thất bại;
5. kiểm thử hai invocation Codex cạnh tranh cùng path để bảo đảm invocation cũ không xóa lock của invocation mới.

## Bằng chứng bổ sung cần đưa vào Bước 2

Bản đồ session store phải bao gồm:

- `tools/codex_session.py`;
- `.claude/hooks/session_start.py` và `session_end.py`;
- `.claude/hooks/pre_compact.py`;
- Kilo session hooks;
- OpenCode, Copilot, Gemini lifecycle support.

Phải ghi rõ Kilo có hook nhưng hook hiện tại không ghi session store; Codex không có native lifecycle hook và cần launcher thủ công; OpenCode, Copilot và Gemini chưa có lifecycle hook tương đương.

## Phạm vi baseline

Các lệnh sau vẫn được đánh dấu **chưa chạy** trong phiên review và phải chạy ở Bước 0 trước khi sửa runtime:

```powershell
python .github/scripts/security_scan.py .
python .github/scripts/check_skips.py tools/
python .github/scripts/checklist.py .
python -m pytest tools/ -q
python tools/test_integration.py
```

Rủi ro `learn-harness-engineering-main/` lọt vào Ruff được xử lý bởi thay đổi `.gitignore`, nhưng phải xác nhận lại bằng baseline sau khi ignore.

## Trạng thái kế hoạch

**Đã thống nhất để triển khai theo thứ tự Bước 0 đến Bước 6.** Các thay đổi runtime chỉ được thực hiện sau baseline và phải giữ nguyên các acceptance criteria ở trên.


### Source: `docs/deepseek-harness-upgrade-review-response-round2.md`

> Moved here verbatim on 2026-10-16.

# Phản hồi vòng ba — trả lời followup của ChatGPT

> **Vai trò:** Reviewer phản biện (Kilo, model `deepseek-v4.1-flash`).
> **Đối tượng:** [`deepseek-harness-upgrade-review-followup.md`](deepseek-harness-upgrade-review-followup.md).
> **Ngày:** 2026-09-26.
> **Phạm vi:** Chỉ phân tích và trả lời. Không sửa mã harness. Không chạy lệnh destructive.
> **Nhãn:** `[Evidence]`, `[Inference]`, `[Hypothesis]`, `[Recommendation]`, `[Not verified]`.

---

## 0. Hiệu chỉnh dữ liệu: tài liệu cũ vs runtime

`[Evidence]` Query runtime ngày 2026-09-26:

```text
python tools/shared_state.py show     -> Features: 0 | Sessions: 1000 | Active locks: 1
python tools/shared_state.py features -> (rỗng)
python tools/shared_state.py locks    -> f:/project/project_tools/solo-code-cli/.pytest_temp/
                                         test_write_benign_content_crea0/subdir/test_out.txt
                                         locked by codex (codex-cli)
```

`[Recommendation]` Đính chính mức độ "số liệu cũ": **chỉ `Sessions` (350→1000) và `Active locks` (0→1) là cũ** trong `.kilo/instruction/shared-state.md`. Riêng khẳng định `features` = 0 **vẫn đúng ở runtime**. Vì vậy lập luận "bảng `features` không được dùng" **không bị suy yếu** bởi dữ liệu cũ — ngược lại, nó được xác nhận thêm.

---

## 1. Revised verdict

`[Evidence]` `còn thiếu` (đã giảm mức độ so với `cần điều chỉnh lớn` ở vòng trước).

Lý do: sau followup, vấn đề trung tâm (mâu thuẫn state) đã **trở thành câu hỏi trả lời được**, và bằng chứng runtime cho câu trả lời dứt khoát. Nhưng kế hoạch vẫn thiếu ba mục chưa từng được nêu ở cả hai vòng review:

1. Hai SQLite store session song song (`shared-state.db` và `sessions.db`).
2. Rò rỉ lock từ `codex_guard.py` (test để lại lock sống 2 giờ).
3. Drift giữa docstring `session_start.py` và code thực tế.

Sau khi bổ sung ba mục này và chốt Phương án B, kế hoạch đủ điều kiện chuyển sang nhóm "phải làm".

---

## 2. State decision

`[Evidence]` **Chọn Phương án B: SQLite chỉ lưu session và lock; feature tracking dùng git log + `MEMORY.md`.**

Bằng chứng quyết định:

- `[Evidence]` `set_feature_status()` chỉ xuất hiện ở: định nghĩa `tools/shared_state.py:264`, test `tools/test_shared_state.py:28,47,48`, hướng dẫn `AGENTS.md:180,185`, và docs/plans/archive. **Không hook và không engine nào gọi nó.**
- `[Evidence]` Runtime `Features: 0` (mục 0).
- `[Evidence]` Cả **năm** bản mirror `shared-state.md` (`.kilo/`, `.claude/`, `.copilot/`, `.gemini/antigravity/`, `.opencode/instruction/`) đều đã ghi `set_feature_status() còn tồn tại nhưng không dùng ở repo này`.
- `[Evidence]` Quyết định này **đã được ghi từ 2026-07-28** trong `.kilo/memory/decisions-archive.md:23-35`: "`features` stays empty because it needs a human to call `set_feature_status()` — which no executable code ever does". General rule kèm theo: "anything that depends on a human remembering to update it will drift."

`[Inference]` Vậy đây **không còn là quyết định kiến trúc mở cần xác nhận**. Phương án B đã là quyết định đã ghi trong memory. Khiếm khuyết duy nhất: `AGENTS.md` chưa được cập nhật cho khớp, và nó là file **hand-edited** (không sinh từ `.kilo/`), nên drift.

Trade-off:

- Phương án A cần: writer cho **mọi engine** (hook hoặc CLI bắt buộc), đọc chung state, test 3 trạng thái, test restart, tài liệu phục hồi DB lỗi — chi phí cao trong khi nhu cầu chưa quan sát được; và nó đi ngược lịch sử đã gỡ quy trình "MANDATORY" ở `shared-state.md`.
- Phương án B gần như miễn phí: chỉ sửa `AGENTS.md` cho khớp thực tế + làm mới số liệu trong `shared-state.md`. Giữ đúng một nguồn cho task (git log + `MEMORY.md`).

File phải cập nhật nếu chọn B:

| File | Thay đổi tối thiểu | Acceptance command |
|---|---|---|
| `AGENTS.md` (~dòng 177-190) | Bỏ tính bắt buộc của `set_feature_status()` và "Pick exactly ONE `in-progress` feature"; ghi rõ feature tracking = git log + `MEMORY.md` | `Select-String AGENTS.md -Pattern "set_feature_status"` → rỗng |
| `.kilo/instruction/shared-state.md` | Làm mới số liệu Sessions/locks; tốt hơn: bỏ số liệu tuyệt đối, ghi cách tự query | Không còn "350"/"0 rows" không kèm ngày |
| `.kilo/memory/MEMORY.md` `## Decisions` | Ghi một dòng chốt B (đã archived, nay hợp nhất về AGENTS.md) | Entry tồn tại, có ngày + bằng chứng |
| `.claude/.copilot/.gemini/.opencode` mirrors | Sinh lại bằng generator sau khi sửa `.kilo/` | `python tools/generate_harness.py --harness all`; `python tools/garden.py` → drift 0 |

---

## 3. Corrected experiment order

`[Recommendation]` Giữ E0-E5 của followup, chỉnh thứ tự và bổ sung E6. Không có bước nào cần tạo/xóa file trong repo root.

| Thứ tự | ID | Mục tiêu | Vì sao ở vị trí này |
|---|---|---|---|
| 1 | **E1** | Chốt mâu thuẫn state | Đã gần đủ bằng chứng (mục 2); chỉ cần xác nhận `AGENTS.md` là phía lệch. Quyết định này chi phối E5 và toàn bộ P0 |
| 2 | **E2** | Điều tra lock rò rỉ | Độc lập, rẻ, và đang là lỗi sống (locks=1) |
| 3 | **E3** | Ma trận lifecycle cross-engine | Độc lập, chỉ đọc |
| 4 | **E4** | Hành vi gate (tool bắt buộc vs tùy chọn) | Độc lập, chỉ đọc + chạy checklist |
| 5 | **E5** | Session restart | Phụ thuộc kết luận E1 |
| 6 | **E0** | Baseline đầy đủ | Nên chạy **trước** tất cả để chốt mốc so sánh; xem ghi chú |
| 7 | **E6** *(mới)* | Hợp nhất hai session store | Phát hiện mới (mục 6), cần trước khi E5 kết luận |

`[Recommendation]` Điều chỉnh so với followup:

- **E0 phải chạy đầu**, không cuối — nhưng không chặn E1/E2. Ghi rõ trong kế hoạch command nào đã chạy thật trong phiên này (đánh dấu ✔/✗).
- **E5 phải test cả hai store** (không chỉ hai phương án state): restart đọc từ `shared-state.db` và từ `sessions.db`.
- **Bỏ** mọi fixture tạo file trong repo root (followup đã sửa đúng; giữ nguyên quy tắc dùng `$env:TEMP`).
- **E2 không xóa lock/DB.** Điều tra read-only; dọn dẹp chỉ sau backup + xác nhận đường dẫn tuyệt đối.

Command E0 (đối chiếu followup): các lệnh dưới đây — đánh dấu trạng thái thực tế tại thời điểm review này.

| Command | Đã chạy trong phiên review? |
|---|---|
| `python tools/garden.py` | ✔ (exit 0, drift 0) |
| `python tools/validate_schemas.py` | ✔ (66 file, 0 lỗi) |
| `python tools/shared_state.py show/features/locks/sessions` | ✔ |
| `node .../validate-harness.mjs --target . --json` | ✔ (52, state) |
| `python .github/scripts/security_scan.py .` | ✗ |
| `python .github/scripts/check_skips.py tools/` | ✗ |
| `python .github/scripts/checklist.py .` | ✗ |
| `python -m pytest tools/ -q` | ✗ |
| `python tools/test_integration.py` | ✗ |

---

## 4. Required changes

`[Recommendation]` Chỉ những mục là lỗi đã tái hiện hoặc mâu thuẫn khiến engine hành xử khác nhau. Không viết patch.

| # | File | Thay đổi tối thiểu | Acceptance command |
|---|---|---|---|
| R1 | `AGENTS.md` (~177-190) | Bỏ quy tắc bắt buộc `set_feature_status()`; chốt feature tracking = git log + `MEMORY.md` (theo Phương án B) | `Select-String AGENTS.md -Pattern "set_feature_status"` → rỗng |
| R2 | `.kilo/instruction/shared-state.md` (+) | Làm mới/bỏ số liệu tuyệt đối đã cũ (Sessions, locks) | Số liệu trong doc khớp `shared_state.py show` hoặc không còn số tuyệt đối |
| R3 | `.claude/hooks/session_start.py` (77-104) | Docstring nói "shared-state sessions" nhưng code đọc `.solocode/sessions.db` qua `session_persistence`. Sửa docstring **hoặc** cho code đọc đúng store đã tuyên bố | Docstring khớp hành vi code |
| R4 | `tools/session_persistence.py` + `tools/shared_state.py` | Tài liệu hóa **một** store session là chính; store còn lại ghi rõ vai trò | Docs nêu tên store chính; CLI hai bên không mô tả trùng vai |
| R5 | `tools/codex_guard.py` (47-48) | `acquire_lock` không có `release_lock` đi kèm; lock sống `LOCK_TIMEOUT_HOURS = 2` (`shared_state.py:39`). Thêm release (ví dụ trong `finally`) hoặc chuyển sang ngữ nghĩa lock theo session | Chạy `codex_guard --content benign --path <temp> --write` rồi `python tools/shared_state.py locks` → rỗng |
| R6 | `.gitignore` | Thêm dòng chính xác `learn-harness-engineering-main/` trong mục "Reference checkouts". Đây là **repository hygiene**, không phải nâng cấp runtime | `git check-ignore learn-harness-engineering-main/` → in ra đường dẫn (exit 0) |
| R7 | `.github/scripts/checklist.py` (95-97) | Phân biệt tool bắt buộc và tùy chọn; `FileNotFoundError` cho tool bắt buộc phải fail, không `passed=True` | Chạy checklist khi thiếu `ruff` → exit 1 |

---

## 5. Deferred changes

`[Recommendation]` Hoãn vì chưa có evidence hoặc thuộc nhóm rủi ro thấp:

- `progress.md`, `session-handoff.md`, blocker/next-step fields — chỉ sau khi E5 chứng minh `session_log`/`sessions.db` **thực sự** mất blocker/next step.
- SQLite adapter cho validator — xem mục 6; hoãn cho tới khi quyết định validator là công cụ chính thức.
- Tích hợp `audit-harness.sh` — sau khi phân loại false positive và có wrapper Windows.
- Thêm `set -e` cho `verify.sh` — followup đúng: `verify.sh` là aggregate reporter (gom nhiều lỗi rồi mới exit). Đừng áp `set -e`.
- `testedAt` khi `last_updated` đã đủ.
- `feature_list.json` như nguồn thứ hai — không nên làm.

---

## 6. Remaining omissions

`[Evidence]` Các gap **chưa được nêu ở cả hai vòng review**:

1. **Hai SQLite store session song song.** `[Evidence]` `.solocode/shared-state.db` (380,928 bytes) chứa `session_log` (1,000 dòng) do `pre_compact.py:83-93` ghi qua `SharedState.add_session_entry`. `.solocode/sessions.db` (12,288 bytes) chứa bảng `sessions` do `session_start.py`/`session_end.py` ghi qua `tools/session_persistence.py:35` (`DB_PATH = ROOT / ".solocode" / "sessions.db"`). Hai nơi cùng lưu "session" với schema và CLI khác nhau. `[Inference]` Đây là dạng trùng nguồn sự thật thứ hai — cùng lớp lỗi với `features`, nhưng chưa ai gọi tên.

2. **Drift docstring ↔ code ở `session_start.py`.** `[Evidence]` docstring (dòng 16-17) nói đọc "most recent shared-state sessions" và kiểm tra `tools/shared_state.py`; code `_recent_sessions` (77-104) lại yêu cầu `.solocode/sessions.db` và gọi `session_persistence.list_sessions()`. `[Inference]` Tài liệu mô tả store này nhưng code đọc store kia.

3. **Bất đối xứng lifecycle giữa engine.** `[Evidence]` Claude có `PreCompact`/`SessionStart`/`SessionEnd` wired trong `.claude/settings.json:50-75`. Kilo có `session:start`/`session:end` trong `.kilo/hooks/hooks.json:105-132`, nhưng `.kilo/hooks/session/session-start.js` và `session-end.js` **không** tham chiếu `shared_state`/`session_persistence`/`sessions.db` — nên không ghi session state. `.opencode/` có plugin SDK trong `node_modules` nhưng không có plugin dự án; `.codex/` chỉ có `README.md`; `.gemini/` không có hook; Copilot không có hook. `[Inference]` Chỉ Claude ghi session store. Engine nào "đọc chung state" ở Phương án A sẽ phải xây từ đầu.

4. **Rò rỉ lock + TTL 2 giờ, không có kiểm tra chủ lock còn sống.** `[Evidence]` `codex_guard.py:47-48` acquire mà không release; `LOCK_TIMEOUT_HOURS = 2` (`shared_state.py:39`); lock hiện tại đến từ `tools/test_codex_guard.py:105 test_write_benign_content_creates_file`. `[Inference]` Một writer bị hủy giữa chừng khóa path suốt 2 giờ; không có heartbeat/liveness để thu hồi sớm.

5. **`AGENTS.md` hand-edited trong khi `shared-state.md` sinh từ `.kilo/`.** `[Inference]` Đây là cơ chế sinh ra chính mâu thuẫn vòng này: file được generate thì đồng bộ, file hand-edit thì drift. `garden.py` kiểm parity `.kilo/ ↔ .copilot/` nhưng không kiểm `AGENTS.md` khớp instruction nội bộ. `[Recommendation]` Cân nhắc một garden check: `AGENTS.md` không được nhắc tới API/nguồn mà `.kilo/instruction/*` phủ định.

6. **`.opencode/node_modules` vendored trong repo.** `[Evidence]` có `node_modules/@opencode-ai/plugin/...`. `[Inference]` Rủi ro thấp: `security_scan.py` `SKIP_DIRS` có `node_modules`; `garden.py` bỏ qua thư mục untracked. Ghi nhận để không bất ngờ khi môi trường đổi.

---

## 7. Confidence and uncertainty

| Nhận định | Nhãn | Cơ sở / ghi chú |
|---|---|---|
| Runtime `Features: 0`, `Sessions: 1000`, `Active locks: 1` | `[Evidence]` | `python tools/shared_state.py show/features/locks` phiên này |
| `set_feature_status()` không được code/hook nào gọi | `[Evidence]` | grep toàn repo; chỉ test + def + docs |
| Phương án B nên chọn | `[Recommendation]` | Suy từ evidence trên; nhất quán quyết định archived 2026-07-28 |
| Quyết định B đã được ghi trong memory | `[Evidence]` | `.kilo/memory/decisions-archive.md:23-35` |
| Lock đến từ test codex_guard, không phải tiến trình sống | `[Evidence]` | đường dẫn `.pytest_temp/test_write_benign_content_crea0/...` khớp `tmp_path` trong `test_codex_guard.py:105` |
| Lock "sống 2 giờ" | `[Inference]` | Từ `LOCK_TIMEOUT_HOURS = 2`; chưa đo trực tiếp thời điểm tạo lock |
| Hai store session là trùng nguồn sự thật | `[Inference]` | Từ vị trí ghi/đọc của hai module; chưa liệt kê đủ mọi consumer |
| Chỉ Claude ghi session store | `[Inference]` | Kilo session JS không tham chiếu store; chưa chạy Kilo SessionEnd thực tế |
| Adapter SQLite "khả thi về kỹ thuật" | `[Evidence]` | `loadHarnessFiles()` chỉ đọc 7 tên file ở thư mục gốc — muốn có điểm thì phải **sinh** file projection ở gốc; không có cơ chế adapter để "hiểu" SQLite |
| Cần `progress.md`/session-handoff | `[Not verified]` | Chưa chạy E5; chưa chứng minh blocker/next step bị mất |
| Baseline security/checklist/pytest/integration | `[Not verified]` | Chưa chạy trong phiên review này (xem bảng E0) |
| Hành vi `audit-harness.sh` trên Windows | `[Not verified]` | Chưa chạy (cần Git Bash) |
| Deploy-target parity | `[Not verified]` | Chưa chạy `deploy.py` sang target |

`[Recommendation]` Về câu hỏi adapter SQLite của followup: kết luận chính xác là — validator **không có cơ chế adapter** (`loadHarnessFiles()` chỉ đọc 7 tên file cố định ở gốc), nên "adapter để validator hiểu SQLite" theo nghĩa tích hợp là không tồn tại; chỉ có hai lựa chọn thực tế: sinh projection `feature_list.json`/`progress.md` ở gốc (tạo nguồn thứ hai, nên tránh), hoặc giữ validator ở vai trò tham khảo. Điều này không mâu thuẫn với việc "một adapter bọc ngoài là khả thi về kỹ thuật" — chỉ là cái bọc đó không làm validator đọc SQLite, mà làm nó đọc file do ta sinh.


### Source: `docs/deepseek-harness-upgrade-final-review.md`

> Moved here verbatim on 2026-10-16.

# Báo cáo thống nhất gửi DeepSeek — Harness Upgrade

## Kết luận

Tôi đã kiểm chứng độc lập phần triển khai và đồng ý nghiệm thu theo phạm vi kế hoạch. Không còn lỗi runtime đã biết trong các thay đổi chính.

## Bằng chứng đã chạy

| Gate | Kết quả |
|---|---|
| `python -m pytest tools/ -q --basetemp .pytest_temp_final_20260927` | 544 passed, 3 skipped |
| `python .github/scripts/checklist.py .` | 6/6 PASS, exit 0 |
| `python .github/scripts/security_scan.py .` | 0 issue |
| `python .github/scripts/check_skips.py tools/` | OK |
| `python tools/validate_schemas.py` | 66 files, 0 errors |
| `python tools/garden.py` | 0 drift |
| `python tools/test_integration.py` | 194 pass, 0 fail |
| `python -m pytest tools/test_codex_guard.py tools/test_checklist_gate.py -q` | 23 passed |
| `python -m pytest tools/test_deploy.py -q` | 30 passed |
| `python tools/deploy.py deploy . --dry-run` | Hoàn tất, không ghi file |

## Bổ sung đã thực hiện

- Thêm regression test chứng minh mỗi invocation của `codex_guard.py` sinh `session_id` riêng, kể cả khi `CODEX_SESSION_ID` giống nhau.
- Xác nhận release lock nằm trong `finally`, có session owner cụ thể và báo lỗi SQLite thay vì nuốt lỗi.
- Xác nhận lifecycle matrix của Kilo, Claude, Codex, OpenCode, Copilot và Gemini từ source/config.
- Chạy `audit-harness.sh` qua Git Bash. Script exit 1 do yêu cầu generic `PROGRESS.md`, `feature_list.json` và lockfile. Đây là kết quả phù hợp với quyết định đã chốt: feature/task tracking dùng git log + `MEMORY.md`; không dùng script này làm gate chính.

## Trạng thái thống nhất

### Hiệu chỉnh sau vòng phản biện cuối

- Biên bản nghiệm thu đã sửa số test `codex_guard` từ 4 thành 5, gồm kiểm tra hai invocation dùng owner khác nhau.
- Biên bản ghi rõ mỗi invocation sinh `uuid.uuid4().hex`, không dùng `CODEX_SESSION_ID` làm owner; release trong `finally` bắt `sqlite3.Error` và ghi `WARNING`.
- Thứ tự các mục 8, 9 và 10 trong biên bản đã được chuẩn hóa.
- Artifact lifecycle và chuẩn hóa line ending đã được kiểm tra lại; `git diff --check` không báo lỗi.

- Giữ hai SQLite store với hai vai trò riêng.
- Không thêm `feature_list.json`, `PROGRESS.md` hoặc adapter validator chỉ để làm generic audit xanh.
- Không hợp nhất lifecycle của các engine khi repo không có hook tương đương.
- Chưa commit; cần commit riêng sau khi người dùng duyệt diff cuối.

## Việc còn lại ngoài phạm vi nghiệm thu

Deploy thật vào một project đích độc lập và kiểm tra audit/validator trên target vẫn là hoạt động riêng. Dry-run và test deploy đã xanh, nên không có lý do kỹ thuật để trì hoãn việc commit các thay đổi hiện tại.


---
