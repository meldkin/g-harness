#!/usr/bin/env python3
"""
solocode-guard (Claude Code hook) — PreToolUse safety gate.

Port of .opencode/plugins/solocode-guard.js to a Claude Code PreToolUse hook.
Stdlib-only Python (no jq/bash) for Windows portability.

Wired via .claude/settings.json:
    "hooks": { "PreToolUse": [ { "matcher": "Bash|Edit|Write|MultiEdit",
        "hooks": [ { "type": "command",
            "command": "python .claude/hooks/guard.py" } ] } ] }

Protocol:
  - Reads the tool call JSON from stdin: {tool_name, tool_input, ...}.
  - Bash: blocks destructive commands and leaked secrets in the command string.
  - Edit/Write/MultiEdit: blocks writes to protected config files and blocks
    content containing hardcoded secrets.
  - Blocks by printing a PreToolUse deny decision to stdout AND exiting 2
    (stderr feedback) — both are honored by Claude Code.
  - Allows by exiting 0 with no output (normal permission flow applies).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ─── Destructive Command Patterns (port of BLOCK_PATTERNS) ──────────────────
# `rm` must sit in COMMAND position -- start of line, after a shell separator, or
# as an xargs target. A bare `rm\s+` also matched `docker run --rm -v /var/...`
# and `rg "rm /" .`, and blocked both. An over-block is worse than a miss here:
# a guard that blocks routine work gets switched off.
_RM_CMD = r"(?:^|[;&|\n]\s*|\bxargs\s+(?:-\S+\s+)*|\b(?:sudo|env|nice|nohup|command|time)\s+(?:\w+=\S*\s+)*)rm\s+(?:--\s+)?"
# Only the flags that make an rm destructive, any order, and at least one of them.
# The `+` is on a flag+separator pair rather than zero-or-more flags: a flagless
# `rm` cannot remove a directory, and matching zero flags made `rm *.tmp` and
# `rm /tmp/test.pid` look like recursive wipes. A bare `[a-zA-Z]` class also
# swallowed `-v` and `-i`.
#
# A short bundle may mix in benign flags alongside the destructive ones (`-rfv`,
# `-fRv`). Requiring the bundle to hold *only* r/R/f/F let `rm -rfv /` through.
# At least one of r/R/f/F must still appear, or rm_system_dir would catch the
# routine `rm -v /var/log/app.log` and the guard would block ordinary logs.
#
# The separator is `\s+`, OR a zero-width boundary at end-of-command. Keeping the
# space inside the flag body made the flags-before-target patterns work but left
# `rm / -rf` (flags last) unmatched -- there is no trailing space to consume.
_RM_FLAG = r"(?:-[a-zA-Z]*[rRfF][a-zA-Z]*|--(?:recursive|force)|--)"
_RM_FLAGS = rf"(?:{_RM_FLAG}(?:\s+|(?=[;&|\n]|$)))+"
# A path that resolves to a filesystem root: `/`, `//`, `/./`, `/.`, `/../`, plus
# the Windows `C:/` and git-bash `/c/` spellings. Matching a bare `/` let
# `rm -rf //` and `rm -rf /./` through; omitting the drive roots let
# `rm -rf C:/` through. An optional leading quote is part of the path, so a
# quoted root (`rm -rf '/'`, `rm -rf "/"`) is still seen as a root.
_ROOT_PATH = r"(?:['\"])?(?:/(?:/|\.+/?)*|[A-Za-z]:[/\\]+|/[A-Za-z]/+)"
# A catastrophic target that may appear BEFORE the flags, as in `rm / -rf`. Reuses
# _ROOT_PATH and adds the whole-system trees and tmp so the flags-after form is
# caught by the same class of rule as the flags-first form. The trailing `/?` lets
# `rm /etc/ -rf` match; a routine file under one of these dirs (`rm /tmp/x.pid`)
# still fails the required `\s+<flags>` and stays allowed.
_TARGET_PATH = rf"(?:{_ROOT_PATH}(?:(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev|tmp)/?)?|~|\*)"

BLOCK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rm_root", re.compile(rf"{_RM_CMD}{_RM_FLAGS}{_ROOT_PATH}(?:\s|$|\*|\"|')")),
    # A root target that is NOT the first argument: `rm -rf build /`. rm_root
    # needs the root directly after the flags, so a second target hid it.
    (
        "rm_root_after_other_target",
        re.compile(rf"{_RM_CMD}{_RM_FLAGS}[^&|;\n]*\s+{_ROOT_PATH}(?:\s|$|\*|\"|')"),
    ),
    # The same wipe with the flags after the target: `rm / -rf`. Each flags-first
    # pattern above needs the flags before its path, so none of them saw this.
    # Benign options may sit on either side of the target and before the
    # destructive flags (`rm -v / -rf`, `rm build / -rf`); the flags still have to
    # be of the r/R/f/F kind, so `rm / -v` (benign only) stays allowed.
    (
        "rm_flags_after_target",
        re.compile(
            rf"{_RM_CMD}(?:[-\w]+\s+)*{_TARGET_PATH}\s+(?:[-\w]+\s+)*{_RM_FLAGS}"
        ),
    ),
    ("rm_home", re.compile(rf"{_RM_CMD}{_RM_FLAGS}~")),
    ("rm_wildcard", re.compile(rf"{_RM_CMD}{_RM_FLAGS}\*")),
    (
        "rm_no_preserve",
        re.compile(rf"{_RM_CMD}.*(?:--no-preserve-root|--preserve-root[=\s]+no)"),
    ),
    # Anchored to command position, and options between `git` and `push` are
    # allowed (`git -C . push --force`). Anchoring keeps a search or a commit
    # message that merely NAMES a force-push from being blocked
    # (`rg 'git push --force main'`, `git commit -m "git push --force main"`).
    (
        "force_push_main",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--force|-f)\s+[^&|;\n]*(?:main|master)"
        ),
    ),
    # The flag may follow the branch, or be absent entirely. The segment stops at
    # a shell separator, because `git push origin main && npm install --force`
    # was being read as a force-push. `-fu` style bundles count (a bare `-f\b`
    # missed them). `--force-with-lease` stays allowed: it is the safe
    # alternative this harness recommends.
    (
        "force_push_any",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--force\b(?!-)|(?:^|\s)(?!-{2})-[a-zA-Z]*f[a-zA-Z]*\b)"
        ),
    ),
    # The `+branch` refspec force-pushes without any flag. AGENTS.md names this
    # exact form as forbidden, and nothing matched it.
    (
        "force_push_refspec",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*\s\+[^\s&|;]+"
        ),
    ),
    # Deleting a protected branch on the remote. `git push origin --delete main`
    # is a force-push in effect (it destroys the remote branch) and nothing
    # matched it: force_push_any only looks for --force/-f. Anchored to command
    # position so a search that merely NAMES it -- `rg 'git push --delete main'`
    # -- is not blocked. git accepts `--delete <remote> <branch>`, so an optional
    # remote token may sit between the flag and the branch. The branch name must
    # be terminated (not `main-fix`), and the `:main` refspec form only counts
    # when the colon opens a token (`origin :main`), so a push to `<src>:main`
    # -- which writes rather than deletes -- is left alone.
    (
        "force_push_delete_main",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--delete\s+|-d\s+|(?:^|\s):)(?:[^\s&|;]+\s+)?(?:refs/heads/)?(?:main|master)(?![\w-])"
        ),
    ),
    # Anchored to the subcommand: `reset` must come directly after `git` (only
    # options may precede it). The unanchored form blocked a commit message that
    # merely mentioned the phrase. `--ha`/`--har` are accepted because git takes
    # unambiguous abbreviations.
    (
        "git_reset_hard",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*reset\b[^&|;\n]*--ha(?:rd?)?"
        ),
    ),
    ("drop_table", re.compile(r"DROP\s+(?:TABLE|DATABASE)", re.I)),
    ("truncate_table", re.compile(r"TRUNCATE\s+TABLE", re.I)),
    ("dd_raw", re.compile(r"dd\s+if=")),
    ("mkfs", re.compile(r"mkfs\.")),
    ("shred", re.compile(r"shred\s+")),
    ("dev_write", re.compile(r">\s*/dev/sd[a-z]")),
    ("win_del_force", re.compile(r"del\s+/f\s+/s")),
    ("win_remove_recursive", re.compile(r"Remove-Item\s+.*-Recurse.*-Force", re.I)),
    # Anchored to a real format invocation: `format` in command position with a
    # drive letter or /fs: switch. A bare \bformat\s also matched
    # `--output-format json`, so the guard blocked ruff and grep -- and a guard
    # that blocks routine tooling teaches people to work around it.
    ("format_disk", re.compile(r"(?:^|[;&|]\s*)format\s+(?:/\S+\s+)*[a-zA-Z]:", re.I)),
    # Anchored to command position: a search or commit message that merely NAMES
    # the command (`rg 'diskpart'`, `rg 'shutdown'`) must not be blocked.
    ("diskpart", re.compile(r"(?:^|[;&|]\s*)diskpart\b")),
    ("shutdown_system", re.compile(r"(?:^|[;&|]\s*)(?:shutdown|reboot|halt)\b")),
    # `./` itself is the target to block (a recursive wipe of the current
    # directory), not any path that merely starts with `.` -- `rm -rf ./build` is
    # routine and was being caught. The trailing boundary keeps `rm -rf ./`
    # (also `./*`, `./ ; ...`) blocked while `rm -rf ./build` is allowed.
    ("rm_relative_wildcard", re.compile(rf"{_RM_CMD}{_RM_FLAGS}\./(?:\s|$|\*)")),
    # A root-relative path that escapes back to root via `..` (`/home/../`,
    # `C:/../`, `/c/../`). _ROOT_PATH stops at the first path segment, so these
    # resolved-to-root wipes were missed; the dirs*fragment steps over the
    # segments before the `..`. The `..` must be the LAST component of the path
    # (optionally chained, `../../`), or a file merely NAMED `..backup`, and a
    # targeted path like `/home/../workspace/build`, would be blocked (§ the
    # `(?:[/\\]\.\.)*[/\\]?(?=\s|$|[;&|*])` tail is what enforces that).
    (
        "rm_root_escape",
        re.compile(
            rf"{_RM_CMD}{_RM_FLAGS}{_ROOT_PATH}(?:[^/\s]+[/\\])*\.\.(?:[/\\]\.\.)*[/\\]?(?=\s|$|[;&|*])"
        ),
    ),
    (
        "git_clean_force",
        re.compile(
            r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*clean\s+-f"
        ),
    ),
    (
        "rm_system_dir",
        re.compile(
            rf"{_RM_CMD}{_RM_FLAGS}{_ROOT_PATH}(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev)(?:/|\s|$)"
        ),
    ),
    # Anchored to command position so a search that merely NAMES the pipe
    # (`rg 'curl http://x | bash'`) is not blocked. Covers piping into a shell
    # (`sh`/`bash`/`zsh`/`ksh`, with or without `sudo`) and into any interpreter
    # that executes the payload (`python`, `perl`, `ruby`, `node`, `pwsh`, `iex`).
    (
        "curl_pipe_shell",
        re.compile(
            r"(?:^|[;&|]\s*)(?:curl|wget)\s+[^|&;\n]*\|\s*(?:(?:sudo|env)\s+(?:\w+=\S*\s+)*)?(?:(?:ba|z|k)?sh\b|python[0-9.]*\b|perl\b|ruby\b|node\b|pwsh\b|powershell\b|iex\b)"
        ),
    ),
    # The PowerShell download-and-execute idiom. curl_pipe_shell only knew the
    # POSIX `| bash`; `irm <url> | iex` runs whatever the URL returns with no
    # file on disk. irm/iwr and Invoke-WebRequest/Invoke-RestMethod are the same
    # cmdlet. Anchored to command position so `rg 'irm x | iex'` is not blocked;
    # piping to Out-File (a file write) is a different, legitimate shape.
    (
        "powershell_download_pipe_iex",
        re.compile(
            r"(?:^|[;&|]\s*)(?:irm|iwr|Invoke-WebRequest|Invoke-RestMethod)\b[^|&;\n]*\|\s*(?:iex|Invoke-Expression)\b",
            re.I,
        ),
    ),
    ("dd_device_write", re.compile(r"dd\s+.*of=/dev/")),
    (
        "chmod_chown_system",
        re.compile(
            r"(?:chmod|chown)\s+-R\s+(?:[^/\s]+\s+)*/(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev)(?:/|\s|$)"
        ),
    ),
    # noqa: S108 -- this is a regex fragment matching the literal path, not a
    # temp path the code uses; splitting the f-string made bandit see `/tmp/` as
    # its own constant and fire hardcoded_tmp_directory.
    ("rm_temp_linux", re.compile(rf"{_RM_CMD}{_RM_FLAGS}/tmp/")),  # noqa: S108
    ("rm_temp_win", re.compile(rf"{_RM_CMD}{_RM_FLAGS}\$?(?:env:)?TEMP\b", re.I)),
    ("del_temp_win", re.compile(r"del\s+(?:/f\s+)?/[qs]\s+\$?(?:env:)?TEMP\b", re.I)),
    ("win_rd_recursive", re.compile(r"(?:rd|rmdir)\s+(?:.*\s)?/s\b", re.I)),
    ("win_del_any", re.compile(r"del\s+(?:.*\s)?/[qsf]\b", re.I)),
    ("win_format_volume", re.compile(r"(?:^|[;&|]\s*)Format-Volume\b", re.I)),
    ("win_stop_computer", re.compile(r"(?:^|[;&|]\s*)Stop-Computer\b", re.I)),
    ("win_restart_computer", re.compile(r"(?:^|[;&|]\s*)Restart-Computer\b", re.I)),
    # Windows disk/registry/shadow-copy destruction the port never carried over.
    # Anchored to command position like format_disk, so a search that only NAMES
    # the cmdlet -- `rg 'reg delete'` -- is not blocked, while each destructive
    # verb still blocks and its read-only sibling (Get-Disk, `reg query`,
    # `vssadmin list shadows`) stays allowed.
    # `reg delete` blocks even a single-value delete (`... /v Cache`) on purpose:
    # the operator asked for `reg delete` wholesale, and a registry write is not
    # regenerable. Narrow it only as a deliberate, reviewed decision.
    ("win_clear_disk", re.compile(r"(?:^|[;&|]\s*)clear-disk\b", re.I)),
    ("win_reg_delete", re.compile(r"(?:^|[;&|]\s*)reg(?:\.exe)?\s+delete\b", re.I)),
    (
        "win_vssadmin_delete",
        re.compile(r"(?:^|[;&|]\s*)vssadmin(?:\.exe)?\s+delete\b", re.I),
    ),
]

# ─── Secret Detection Patterns (port of SECRET_PATTERNS) ────────────────────
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    (
        "aws_secret_key",
        re.compile(
            r"(?:aws|amazon).{0,20}(?:secret|key|token).{0,10}[:=]\s*[\"'][A-Za-z0-9/+=]{20,}",
            re.I,
        ),
    ),
    # `(?!\$)` keeps a quoted *reference* out of the block list: the old pattern
    # blocked `API_KEY="$(op read op://vault/key)"`, which pushed users toward
    # inlining the literal secret instead of resolving it at runtime.
    (
        "generic_api_key",
        re.compile(
            r"(?:api[_-]?key|apikey|secret|password)\s*[:=]\s*[\"'](?!\$)[^\"']{8,}[\"']",
            re.I,
        ),
    ),
    # Unquoted `NAME=value` assignments. `generic_api_key` above requires quotes,
    # so `export COMMANDCODE_API_KEY=<token>` and `AWS_SECRET_ACCESS_KEY=<token>`
    # both passed straight through -- the exact forms an agent types when it
    # means to use a key. The `[a-z_-]*` tail matches the `_ACCESS_KEY` /
    # `_TOKEN` compound names. Two exclusions keep the detector honest:
    #   `[^\s\"'$]` first char -> `KEY="$(op read ...)"` and `KEY=${VAR:-}` are
    #     references, not literals, and must not block.
    #   the lookahead -> `sk-ant-xxxxxxxxxxxx` is a doc placeholder, and
    #     `MUST_NOT_DETECT[markdown_placeholder]` pins that it stays allowed.
    (
        "env_assignment_secret",
        re.compile(
            r"(?:api[_-]?key|secret|token|password|passwd|credential)[a-z_-]*\s*[:=]\s*(?![^\s\"']*(?:x{3}|\*{3}))[^\s\"'$][^\s\"']{15,}",
            re.I,
        ),
    ),
    (
        "private_key_pem",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "jwt_token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    (
        "github_token",
        re.compile(
            r"(?:gh[pousr]_|github[_-]?pat[_-]?|github[_-]?token[_-]?)[A-Za-z0-9_]{20,}",
            re.I,
        ),
    ),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("stripe_key", re.compile(r"(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}")),
    ("mongodb_uri", re.compile(r"mongodb(?:\+srv)?://[^:]+:[^@]+@")),
    ("postgres_uri", re.compile(r"postgres(?:ql)?://[^:]+:[^@]+@")),
    ("redis_uri", re.compile(r"redis://[^:]+:[^@]+@")),
    (
        "hardcoded_token",
        re.compile(
            r"(?:token|bearer)\s*[:=]\s*[\"'][A-Za-z0-9._\-+/=]{20,}[\"']", re.I
        ),
    ),
    (
        "discord_webhook",
        re.compile(
            r"https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+", re.I
        ),
    ),
    ("basic_auth", re.compile(r"https?://[^:]+:[^@]+@")),
    # Prefixed-token formats. `generic_api_key` only fires on a QUOTED value,
    # so bare `KEY=sk-ant-...` shell/env forms passed straight through -- this
    # project's own Anthropic key format included. Length floors sit above
    # doc-placeholder length so README examples do not trip the gate.
    # Pinned by tools/test_secret_patterns.py.
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{24,}")),
    ("openai_project_key", re.compile(r"sk-proj-[A-Za-z0-9\-_]{20,}")),
    ("npm_token", re.compile(r"npm_[A-Za-z0-9]{36}")),
    ("gitlab_pat", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}")),
    ("digitalocean_token", re.compile(r"dop_v1_[A-Za-z0-9]{64}")),
    # Authorization header form: no quotes, no "=", so `hardcoded_token` missed it.
    # `re.I` is required: `authorization: bearer <tok>` (lowercase) is what curl
    # examples actually use, and it passed the case-sensitive form.
    ("bearer_header", re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]{20,}", re.I)),
    # Legacy bare `sk-` keys with no recognised prefix. Mirrors
    # .github/scripts/security_scan.py. Does not overlap `anthropic_key`: that
    # needs 24 contiguous chars after `sk-ant-`, and this needs 20 contiguous
    # alphanumerics right after `sk-`, which the `-` in `sk-ant-` breaks.
    ("openai_legacy_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
]

# ─── Protected Config Files (port of PROTECTED_FILES) ───────────────────────
PROTECTED_FILES: frozenset[str] = frozenset(
    {
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.cjs",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
        "eslint.config.ts",
        "eslint.config.mts",
        "eslint.config.cts",
        ".prettierrc",
        ".prettierrc.js",
        ".prettierrc.cjs",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".prettierrc.yaml",
        "prettier.config.js",
        "prettier.config.cjs",
        "prettier.config.mjs",
        "biome.json",
        "biome.jsonc",
        ".ruff.toml",
        "ruff.toml",
        ".shellcheckrc",
        ".stylelintrc",
        ".stylelintrc.json",
        ".stylelintrc.yml",
        ".markdownlint.json",
        ".markdownlint.yaml",
        ".markdownlintrc",
        ".flake8",
        ".pylintrc",
        "tox.ini",
        ".golangci.yml",
        ".golangci.yaml",
        ".golangci.json",
        ".editorconfig",
    }
)


def normalize_command(command: str) -> str:
    """Strip sudo/env/bash -c wrappers + collapse whitespace to defeat bypasses."""
    if not command or not isinstance(command, str):
        return ""
    cmd = re.sub(r"\s+", " ", command).strip()
    while True:
        prev = cmd
        cmd = re.sub(r"^sudo\s+", "", cmd)
        cmd = re.sub(r"^env(\s+\w+=[^\s]*)+\s+", "", cmd)
        cmd = re.sub(r"^(?:bash|sh)\s+-c\s+", "", cmd)
        cmd = re.sub(r"^(?:nohup|nice|command|time)\s+", "", cmd)
        cmd = re.sub(r"^(['\"])(.*)\1$", r"\2", cmd)
        if cmd == prev:
            break
    cmd = re.sub(r"^/?(?:[\w.-]+/)+([\w.-]+)", r"\1", cmd)
    return cmd


def find_destructive(command: str) -> str | None:
    for raw in (command, normalize_command(command)):
        if not raw:
            continue
        for name, pattern in BLOCK_PATTERNS:
            if pattern.search(raw):
                return name
    return None


def find_secret(text: str) -> str | None:
    if not text:
        return None
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None


# ─── Skill risk declaration ─────────────────────────────────────────────────
#
# A skill that TELLS the agent to run a side-effecting command (deploy, push,
# migrate) must declare `risk: side-effecting` in its frontmatter. The point is
# not the label -- it is that adding such an instruction becomes a deliberate,
# visible act instead of a line that slips into a skill silently.
#
# Only fires on imperative instructions ("Run the migration", "Deploy the ...")
# so a skill may still freely NAME a command: permission-guard documents
# `rm -rf` precisely because it blocks it, and must not be forced to declare
# itself side-effecting for doing so.

SKILL_RISK_VALUES = {"none", "side-effecting"}

_SIDE_EFFECT_INSTRUCTION = re.compile(
    r"^\s*(?:[-*]|\d+\.)?\s*(?:Run|Execute|Push|Deploy|Apply|Publish|Release)\b"
    r"[^\n]*?(git\s+push|deploy|migrat|reset\s+--hard|--force)",
    re.I | re.M,
)


def parse_frontmatter_value(content: str, key: str) -> str | None:
    """Read one top-level scalar from a `---`-delimited frontmatter block."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    for line in content[3:end].splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.*)$", line.strip())
        if m:
            return m.group(1).strip().strip("\"'")
    return None


def check_skill_risk(
    file_path: str, content: str, *, is_full_content: bool
) -> str | None:
    """Return a denial reason if a SKILL.md's risk declaration is wrong.

    Content-based, not path-based: the check reads what the skill instructs,
    so it cannot be bypassed by writing the file somewhere else first.

    A partial Edit supplies only the replacement fragment, which carries no
    frontmatter -- reading `risk:` from it would report "not declared" for
    every skill, including correctly-declared ones. So for fragments the
    declaration is read from the file on disk instead.
    """
    if os.path.basename(file_path) != "SKILL.md" or not content:
        return None

    declared_source = content
    if not is_full_content:
        try:
            with open(file_path, encoding="utf-8") as fh:
                declared_source = fh.read()
        except OSError:
            # New file via Edit, or unreadable: no frontmatter to judge
            # against, so stay silent rather than block on a guess.
            return None

    declared = parse_frontmatter_value(declared_source, "risk")
    if declared is not None and declared not in SKILL_RISK_VALUES:
        return (
            f"SKILL.md declares unknown risk '{declared}'. "
            f"Use one of: {', '.join(sorted(SKILL_RISK_VALUES))}."
        )

    hit = _SIDE_EFFECT_INSTRUCTION.search(content)
    if hit and declared != "side-effecting":
        return (
            f"SKILL.md instructs a side-effecting action "
            f"({hit.group(0).strip()[:60]!r}) but does not declare "
            f"'risk: side-effecting' in its frontmatter. Add it, or "
            f"reword so the skill describes rather than instructs."
        )
    return None


def deny(reason: str) -> None:
    """Emit a Claude PreToolUse deny decision and exit non-zero."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    print(f"[solocode-guard] BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)


# ─── Executor Mode (orchestrator/executor split) ────────────────────────────
# When enabled, the orchestrator (Claude) may not write files directly: code
# changes must be routed to a worker engine (Kilo CLI/DeepSeek, gpt-5.6-sol) via
# tools/kilo_cli_delegate.py. Claude keeps planning, reviewing and verifying.
#
# State lives in .solocode/executor-mode (gitignored, per-machine):
#   file absent            -> ENABLED  (default-on, by design)
#   file contains off|0|disabled|false -> disabled
#   any other content      -> ENABLED
#
# SCOPE, STATED HONESTLY: this gates Edit/Write/MultiEdit only. Bash is
# deliberately NOT gated, so `python -c`, heredocs, `sed -i` and `>` still
# write files. This is a speed bump plus an audit trail, not a sandbox --
# chosen over a stricter gate because Bash-write blocking is an unwinnable
# arms race that also breaks legitimate verification scripts.
EXECUTOR_MODE_OFF_VALUES: frozenset[str] = frozenset(
    {
        "off",
        "0",
        "disabled",
        "false",
        "no",
    }
)

# Paths the orchestrator must still write for delegation itself to work.
# Kept deliberately short: every entry is a hole in the gate.
EXECUTOR_MODE_ALLOWED_PREFIXES: tuple[str, ...] = (
    # Gemini/Antigravity handoff briefs -- writing the plan IS the delegation.
    ".gemini/antigravity/handoff/inbox/",
    # The toggle itself, so the mode can be turned off without hand-editing.
    ".solocode/executor-mode",
)


def project_root() -> Path:
    """Repo root: CLAUDE_PROJECT_DIR if set, else this hook's grandparent."""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent.parent


def executor_mode_enabled(root: Path | None = None) -> bool:
    """True when the orchestrator must delegate writes. Default: True."""
    root = root or project_root()
    state_file = root / ".solocode" / "executor-mode"
    try:
        raw = state_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return True  # Absent or unreadable -> default-on.
    return raw.strip().split("#", 1)[0].strip().lower() not in EXECUTOR_MODE_OFF_VALUES


def executor_mode_exempt(file_path: str, root: Path | None = None) -> bool:
    """True if this path is delegation plumbing that stays writable."""
    if not file_path:
        return False
    root = root or project_root()
    path = Path(file_path)
    try:
        rel = (path if path.is_absolute() else root / path).resolve()
        rel_str = rel.relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        # Outside the repo (or unresolvable): not delegation plumbing.
        rel_str = path.as_posix().lstrip("./")
    return rel_str.startswith(EXECUTOR_MODE_ALLOWED_PREFIXES)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # No parseable input — do not block.

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool == "Bash":
        command = tool_input.get("command", "") or ""
        hit = find_destructive(command)
        if hit:
            deny(
                f"destructive command pattern '{hit}' detected. "
                f"Run manually if you are certain this is safe."
            )
        secret = find_secret(command)
        if secret:
            deny(
                f"possible secret '{secret}' in command. Use environment variables instead."
            )
        return 0

    if tool in ("Edit", "Write", "MultiEdit"):
        file_path = tool_input.get("file_path", "") or ""
        basename = os.path.basename(file_path)
        if basename in PROTECTED_FILES:
            deny(
                f"'{basename}' is a protected config file. Confirm before editing linter/formatter config."
            )
        # Scan proposed content for secrets.
        full_content = tool_input.get("content", "") or ""
        content = full_content or tool_input.get("new_string", "") or ""
        fragments = tool_input.get("edits", []) or []
        for edit in fragments:
            content += "\n" + (edit.get("new_string", "") or "")
        secret = find_secret(content)
        if secret:
            deny(
                f"possible secret '{secret}' in file content. Use environment variables instead."
            )
        risk_issue = check_skill_risk(
            file_path,
            content,
            is_full_content=bool(full_content) and not fragments,
        )
        if risk_issue:
            deny(risk_issue)
        # Executor mode last: the security denials above carry more specific,
        # more urgent messages, so they should win when both would fire.
        if executor_mode_enabled() and not executor_mode_exempt(file_path):
            deny(
                f"executor mode is ON -- the orchestrator does not write files "
                f"directly. Route this change to a worker:\n"
                f'  python tools/opencode_delegate.py "<self-contained task naming '
                f'{file_path}>" --free\n'
                f"Then verify the result yourself (read the file back, run the "
                f"gates) before accepting it. Note: workers can misreport which "
                f"path they wrote -- confirm with git status.\n"
                f"To disable: echo off > .solocode/executor-mode"
            )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
