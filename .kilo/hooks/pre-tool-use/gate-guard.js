#!/usr/bin/env node
/**
 * gate-guard.js — PreToolUse hook for Solo-Code-Harness
 *
 * Validates shell commands with 7 category patterns + safe alternatives.
 * Upgraded from Claude Code version validate_bash.py.
 *
 * Categories:
 *   BLOCK (exit 2), WARN, PATH, MODE, SED, SEMANTIC, PIPE
 *
 * Exit codes: 0 = ALLOW, 2 = BLOCK
 *
 * Cross-platform tool name support:
 *   Claude Code: Bash | Kilo: bash | Gemini: run_command, execute
 *   Copilot: runCommand, terminal | Cursor: execute_command
 */

'use strict';

const MAX_STDIN = 1024 * 1024;

// ─── BLOCK PATTERNS (exit 2) ───────────────────────────────────────────────
// Kept 1:1 with .claude/hooks/guard.py. Kilo previously enforced a strictly
// weaker set than Claude: rm_system_dir, rm_temp_linux, chmod_chown_system and
// thirteen others were missing here, so `rm -rf /etc` blocked under Claude and
// passed under Kilo.
//
// `rm` must sit in COMMAND position -- start of line, after a shell separator, or
// as an xargs target. A bare `rm\s+` also matched `docker run --rm -v /var/...`
// and `rg "rm /" .`, and blocked both. An over-block is worse than a miss here:
// a guard that blocks routine work gets switched off.
//
// The `bash|sh -c '...'` and `sudo`/`env` wrappers are unwrapped by
// normalizeCommand() below before patterns run, exactly as guard.py unwraps them
// in normalize_command(). Handling them here instead caused a divergence: Kilo
// blocked `echo "bash -c 'rm -rf /'"` (matched the quoted wrapper) while Claude
// allowed it.
const RM_CMD = '(?:^|[;&|\\n]\\s*|\\bxargs\\s+(?:-\\S+\\s+)*|\\b(?:sudo|env|nice|nohup|command|time)\\s+(?:\\w+=\\S*\\s+)*)rm\\s+(?:--\\s+)?';
// At least one destructive flag (`+` on a flag+separator pair): a flagless `rm`
// cannot remove a directory, and matching zero flags made `rm *.tmp` and
// `rm /tmp/test.pid` look like recursive wipes. A short bundle may mix in benign
// flags (`-rfv`) -- requiring only r/R/f/F let `rm -rfv /` through -- but at
// least one of r/R/f/F must appear, or rm_system_dir would catch
// `rm -v /var/log/app.log`. The separator may be a zero-width boundary at
// end-of-command so `rm / -rf` (flags last) matches too.
const RM_FLAG = '(?:-[a-zA-Z]*[rRfF][a-zA-Z]*|--(?:recursive|force)|--)';
const RM_FLAGS = '(?:' + RM_FLAG + '(?:\\s+|(?=[;&|\\n]|$)))+';
// A path resolving to a filesystem root: `/`, `//`, `/./`, `/.`, `/../`, plus
// the Windows `C:/` and git-bash `/c/` spellings. An optional leading quote is
// part of the path, so `rm -rf '/'` / `rm -rf "/"` are still roots.
const ROOT_PATH = '[\'"]?(?:/(?:/|\\.+/?)*|[A-Za-z]:[/\\\\]+|/[A-Za-z]/+)';
// A catastrophic target that may appear BEFORE the flags, as in `rm / -rf`:
// ROOT_PATH plus the whole-system trees and tmp. A routine file under one of
// those dirs (`rm /tmp/x.pid`) still fails the required `\s+<flags>`.
const TARGET_PATH = '(?:' + ROOT_PATH + '(?:(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev|tmp)/?)?|~|\\*)';
const BLOCK_PATTERNS = [
  { name: 'rm_root', pattern: new RegExp(RM_CMD + RM_FLAGS + ROOT_PATH + '(?:\\s|$|\\*|"|\')') },
  // A root target that is not the first argument: `rm -rf build /`.
  { name: 'rm_root_after_other_target', pattern: new RegExp(RM_CMD + RM_FLAGS + '[^&|;\\n]*\\s+' + ROOT_PATH + '(?:\\s|$|\\*|"|\')') },
  { name: 'rm_flags_after_target', pattern: new RegExp(RM_CMD + TARGET_PATH + '\\s+' + RM_FLAGS) },
  { name: 'rm_home', pattern: new RegExp(RM_CMD + RM_FLAGS + '~') },
  { name: 'rm_wildcard', pattern: new RegExp(RM_CMD + RM_FLAGS + '\\*') },
  { name: 'rm_relative_wildcard', pattern: new RegExp(RM_CMD + RM_FLAGS + '\\./(?:\\s|$|\\*)') },
  // A root-relative path that escapes back to root via `..` (`/home/../`,
  // `C:/../`, `/c/../`): ROOT_PATH stops at the first segment, so the dirs*
  // fragment steps over the segments before the `..`. The `..` must end the path
  // (optionally chained) so a file named `..backup`, or a targeted path like
  // `/home/../workspace/build`, is not blocked.
  { name: 'rm_root_escape', pattern: new RegExp(RM_CMD + RM_FLAGS + ROOT_PATH + '(?:[^/\\s]+[/\\\\])*\\.\\.(?:[/\\\\]\\.\\.)*[/\\\\]?(?=\\s|$|[;&|*])') },
  { name: 'rm_no_preserve', pattern: new RegExp(RM_CMD + '.*(?:--no-preserve-root|--preserve-root[=\\s]+no)') },
  { name: 'rm_system_dir', pattern: new RegExp(RM_CMD + RM_FLAGS + ROOT_PATH + '(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev)(?:/|\\s|$)') },
  { name: 'rm_temp_linux', pattern: new RegExp(RM_CMD + RM_FLAGS + '/tmp/') },
  { name: 'rm_temp_win', pattern: new RegExp(RM_CMD + RM_FLAGS + '\\$?(?:env:)?TEMP\\b', 'i') },
  { name: 'del_temp_win', pattern: /del\s+(?:\/f\s+)?\/[qs]\s+\$?(?:env:)?TEMP\b/i },
  { name: 'force_push_main', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--force|-f)\s+[^&|;\n]*(?:main|master)/ },
  // The segment stops at a shell separator, because
  // `git push origin main && npm install --force` was being read as a force-push.
  // `-fu` style bundles count (a bare `-f\b` missed them). `--force-with-lease`
  // stays allowed: it is the safe alternative this harness recommends. Anchored
  // to command position so `rg 'git push --force main'` and a commit message that
  // merely NAMES a force-push are not blocked. Options between `git` and `push`
  // are allowed (`git -C . push --force`).
  { name: 'force_push_any', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--force\b(?!-)|(?:^|\s)(?!-{2})-[a-zA-Z]*f[a-zA-Z]*\b)/ },
  // The `+branch` refspec force-pushes without any flag. AGENTS.md names this
  // exact form as forbidden, and nothing matched it.
  { name: 'force_push_refspec', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*\s\+[^\s&|;]+/ },
  // Deleting a protected branch on the remote: a force-push in effect, and
  // nothing matched it before. Anchored to command position so a search that
  // only NAMES it (`rg 'git push --delete main'`) is not blocked; git accepts
  // `--delete <remote> <branch>`, so an optional remote may precede the branch.
  // The name must be terminated (not `main-fix`), and the `:main` refspec only
  // counts when the colon opens a token, so a push to `<src>:main` (which
  // writes) is left alone.
  { name: 'force_push_delete_main', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*push\b[^&|;\n]*(?:--delete\s+|-d\s+|(?:^|\s):)(?:[^\s&|;]+\s+)?(?:refs\/heads\/)?(?:main|master)(?![\w-])/ },
  // Anchored to the subcommand so a commit message that merely mentions the
  // phrase is not blocked. `--ha`/`--har` count: git takes abbreviations.
  { name: 'git_reset_hard', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*reset\b[^&|;\n]*--ha(?:rd?)?/ },
  { name: 'git_clean_force', pattern: /(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--\S+\s+)*clean\s+-f/ },
  { name: 'drop_table', pattern: /DROP\s+(?:TABLE|DATABASE)/i },
  { name: 'truncate_table', pattern: /TRUNCATE\s+TABLE/i },
  { name: 'dd_raw', pattern: /dd\s+if=/ },
  { name: 'dd_device_write', pattern: /dd\s+.*of=\/dev\// },
  { name: 'mkfs', pattern: /mkfs\./ },
  { name: 'shred', pattern: /shred\s+/ },
  { name: 'dev_write', pattern: />\s*\/dev\/sd[a-z]/ },
  // Anchored to command position; wrappers (`sudo`, `bash -c`) are handled by
  // normalizeCommand() so a search that merely NAMES the pipe is not blocked
  // while a wrapped one is caught and the engines agree. Covers piping into a
  // shell (sh/bash/zsh/ksh, with or without sudo) and into an interpreter that
  // executes the payload (python, perl, ruby, node, pwsh, iex).
  { name: 'curl_pipe_shell', pattern: /(?:^|[;&|]\s*)(?:curl|wget)\s+[^|&;\n]*\|\s*(?:sudo\s+)?(?:(?:ba|z|k)?sh\b|python[0-9.]*\b|perl\b|ruby\b|node\b|pwsh\b|powershell\b|iex\b)/ },
  // The PowerShell download-and-execute idiom (`irm <url> | iex`), which runs
  // whatever the URL returns with no file on disk. Anchored to command position
  // so `rg 'irm x | iex'` is not blocked. Piping to Out-File is a different,
  // legitimate shape.
  { name: 'powershell_download_pipe_iex', pattern: /(?:^|[;&|]\s*)(?:irm|iwr|Invoke-WebRequest|Invoke-RestMethod)\b[^|&;\n]*\|\s*(?:iex|Invoke-Expression)\b/i },
  { name: 'chmod_chown_system', pattern: /(?:chmod|chown)\s+-R\s+(?:[^\/\s]+\s+)*\/(?:etc|usr|var|bin|lib(?:64)?|boot|sbin|opt|root|sys|proc|dev)(?:\/|\s|$)/ },
  { name: 'win_del_force', pattern: /del\s+\/f\s+\/s/ },
  { name: 'win_rd_recursive', pattern: /(?:rd|rmdir)\s+(?:.*\s)?\/s\b/i },
  { name: 'win_del_any', pattern: /del\s+(?:.*\s)?\/[qsf]\b/i },
  { name: 'win_remove_recursive', pattern: /Remove-Item\s+.*-Recurse.*-Force/i },
  { name: 'win_format_volume', pattern: /\bFormat-Volume\b/ },
  { name: 'win_stop_computer', pattern: /\bStop-Computer\b/ },
  { name: 'win_restart_computer', pattern: /\bRestart-Computer\b/ },
  // Windows disk/registry/shadow-copy destruction the port never carried over.
  // Anchored to command position like format_disk, so `rg 'reg delete'` is not
  // blocked while Get-Disk / `reg query` / `vssadmin list shadows` stay allowed.
  // `reg delete` blocks a single-value delete (`... /v Cache`) on purpose -- the
  // operator asked for it wholesale; a registry write is not regenerable.
  { name: 'win_clear_disk', pattern: /(?:^|[;&|]\s*)clear-disk\b/i },
  { name: 'win_reg_delete', pattern: /(?:^|[;&|]\s*)reg(?:\.exe)?\s+delete\b/i },
  { name: 'win_vssadmin_delete', pattern: /(?:^|[;&|]\s*)vssadmin(?:\.exe)?\s+delete\b/i },
  // Anchored to a real format invocation: `format` in command position with a
  // drive letter or /fs: switch. A bare /\bformat\s/ also matched
  // `--output-format json`, so the guard blocked ruff and grep -- and a guard
  // that blocks routine tooling teaches people to work around it.
  { name: 'format_disk', pattern: /(?:^|[;&|]\s*)format\s+(?:\/\S+\s+)*[a-zA-Z]:/i },
  { name: 'diskpart', pattern: /\bdiskpart\b/ },
  { name: 'shutdown_system', pattern: /(?:shutdown|reboot|halt)\b/ },
];

// ─── WARN PATTERNS ─────────────────────────────────────────────────────────
const WARN_PATTERNS = [
  { name: 'npm_global', pattern: /npm\s+install\s+-g/,
    message: 'npm install -g: global install — prefer local or npx' },
  { name: 'pip_solo', pattern: /pip\s+install\s+(?!-r|\.)/,
    message: 'pip install: consider adding to requirements.txt' },
  { name: 'curl_pipe_bash', pattern: /curl\s+.*\|\s*(?:ba)?sh/,
    message: 'curl | sh: piping to shell is unsafe. Review script first' },
  { name: 'eval_injection', pattern: /(?:eval|exec)\(.*\$/,
    message: 'eval/exec with variable input — code injection risk' },
  { name: 'debug_code', pattern: /console\.log\(|debugger;/,
    message: 'Debug code detected — remove before committing' },
];

// ─── PATH VALIDATION ───────────────────────────────────────────────────────
const PATH_WARN = [
  { name: 'tmp_volatile', pattern: /\b\/tmp\//,
    message: 'Writing to /tmp — data lost on reboot. Use persistent path.' },
  { name: 'tilde_expand', pattern: /\b~\//,
    message: 'Tilde ~ in script — may not expand as expected. Use $HOME.' },
  { name: 'deep_relative', pattern: /(?<!\w)\.\.\/\.\.\//,
    message: 'Deep relative path — fragile. Use absolute or project-relative.' },
];

// ─── MODE/PERMISSION VALIDATION ─────────────────────────────────────────────
const MODE_WARN = [
  { name: 'chmod_777', pattern: /chmod\s+.*777/,
    message: 'chmod 777 — world-writable. Use 755 or 644 instead.' },
  { name: 'chmod_plusx', pattern: /chmod\s+.*\+x\s+(?!.*\.sh)/,
    message: 'chmod +x on non-script file — verify intent.' },
];

// ─── SED/SYNTAX VALIDATION ─────────────────────────────────────────────────
const SED_WARN = [
  { name: 'piped_sed', pattern: /sed\s+.*\|.*sed/,
    message: 'Piped sed commands — fragile. Use single sed with -e.' },
  { name: 'sed_no_backup', pattern: /sed\s+-i\s+(?!.*\.bak)/,
    message: 'sed -i without .bak — no backup. Use sed -i.bak.' },
];

// ─── SEMANTIC VALIDATION ───────────────────────────────────────────────────
const SEMANTIC_WARN = [
  { name: 'kill_minus9', pattern: /kill\s+-9/,
    message: 'kill -9 is SIGKILL — no cleanup. Try kill -15 first.' },
  { name: 'docker_rm_force', pattern: /docker\s+rm\s+-f/,
    message: 'docker rm -f — force remove. May orphan resources.' },
  { name: 'npm_audit_force', pattern: /npm\s+audit\s+fix\s+--force/,
    message: 'npm audit fix --force — may break deps. Review first.' },
  { name: 'git_stash_drop', pattern: /git\s+stash\s+drop/,
    message: 'git stash drop — irreversible. Use git stash pop first.' },
];

// ─── PIPED DESTRUCTIVE ─────────────────────────────────────────────────────
const PIPE_DESTRUCTIVE = [
  { name: 'xargs_rm', pattern: /xargs\s+rm/,
    message: 'xargs rm — batch deletion. Review what xargs receives.' },
  { name: 'find_delete', pattern: /find\s+.*-delete/,
    message: 'find -delete — direct deletion. Use -print first to preview.' },
  { name: 'find_exec_rm', pattern: /find\s+.*-exec\s+rm/,
    message: 'find -exec rm — deletion via find. Use -print first to preview.' },
  { name: 'batch_branch_delete', pattern: /git\s+branch\s+.*\|.*xargs.*git\s+branch\s+-D/,
    message: 'Batch branch deletion — verify which branches will be deleted first.' },
  { name: 'kubectl_delete_all', pattern: /kubectl\s+delete\s+.*--all/,
    message: 'kubectl delete --all — deletes all resources in namespace.' },
];

// ─── SAFE ALTERNATIVES ─────────────────────────────────────────────────────
const SAFE_ALTERNATIVES = [
  { cmd: 'rm -rf', alt: 'mv <path> /tmp/<name>-backup first, then rm after verifying' },
  { cmd: 'rm ',    alt: 'Use mv to trash or add .bak suffix before deleting' },
  { cmd: 'git reset --hard', alt: 'Use git stash + git reset --soft to preserve changes' },
  { cmd: 'git push --force', alt: 'Use git push --force-with-lease to avoid overwriting' },
  { cmd: 'git branch -D', alt: 'Use git branch -d (lowercase) for merged branches only' },
  { cmd: 'docker rm -f', alt: 'Use docker stop first, then docker rm' },
  { cmd: 'kill -9', alt: 'Use kill -15 (SIGTERM) first for clean shutdown' },
];

// ─── Helpers ────────────────────────────────────────────────────────────────

// Port of guard.py's normalize_command(): both engines must unwrap the same
// wrappers or their verdicts diverge (Python normalises `sudo git push …`, so
// without this Kilo allowed what Claude blocked). Rules match Python exactly:
// collapse whitespace, strip a leading sudo / `env KEY=VAL…` / `bash|sh -c`,
// strip a fully surrounding quote pair, strip a leading path.
function normalizeCommand(command) {
  if (!command || typeof command !== 'string') return '';
  let cmd = command.replace(/\s+/g, ' ').trim();
  for (;;) {
    const prev = cmd;
    cmd = cmd.replace(/^sudo\s+/, '');
    cmd = cmd.replace(/^env(?:\s+\w+=[^\s]*)+\s+/, '');
    cmd = cmd.replace(/^(?:bash|sh)\s+-c\s+/, '');
    cmd = cmd.replace(/^(['"])(.*)\1$/, '$2');
    if (cmd === prev) break;
  }
  cmd = cmd.replace(/^\/?(?:[\w.-]+\/)+([\w.-]+)/, '$1');
  return cmd;
}

function checkPatterns(patterns, command) {
  for (const { name, pattern, message } of patterns) {
    try {
      if (pattern.test(command)) {
        return { name, message: message || name };
      }
    } catch {}
  }
  return null;
}

function checkAlternatives(command) {
  return SAFE_ALTERNATIVES
    .filter(({ cmd }) => command.includes(cmd))
    .map(({ cmd, alt }) => `  ${cmd} → ${alt}`);
}

function isSensitivePath(filePath) {
  const sensitive = [/\.env(?:\.\w+)?$/i, /credentials\./i, /secrets?\./i, /\.pem$/i, /\.key$/i, /id_rsa/];
  return sensitive.some(p => p.test(filePath));
}

// ─── Main ───────────────────────────────────────────────────────────────────
let raw = '';
let truncated = false;

process.stdin.setEncoding('utf8');
process.stdin.resume();
process.stdin.on('data', chunk => {
  if (raw.length < MAX_STDIN) {
    const remaining = MAX_STDIN - raw.length;
    raw += chunk.substring(0, remaining);
    if (chunk.length > remaining) truncated = true;
  } else {
    truncated = true;
  }
});

process.stdin.on('end', () => {
  process.stdout.write(raw);

  if (truncated) {
    process.stderr.write('[GateGuard] Input truncated (>1MB) — allowing, cannot inspect\n');
    process.exit(0);
  }

  let input;
  try { input = JSON.parse(raw); } catch { process.exit(0); }

  // Cross-platform shell tool names
  const SHELL_TOOLS = new Set([
    'Bash', 'bash',           // Claude Code, Kilo
    'run_command', 'execute', // Gemini/Antigravity
    'runCommand', 'terminal', // Copilot
    'execute_command', 'shell', 'RunCommand', // Cursor, generic
  ]);

  const toolName = input.tool_name || '';
  const toolInput = input.tool_input || {};

  if (SHELL_TOOLS.has(toolName)) {
    const command = toolInput.command || toolInput.CommandLine || toolInput.cmd || toolInput.commandLine || '';

    // 1. BLOCK destructive patterns (raw, then unwrapped -- mirrors guard.py's
    //    find_destructive, which checks command and normalize_command(command))
    const blocked =
      checkPatterns(BLOCK_PATTERNS, command) ||
      checkPatterns(BLOCK_PATTERNS, normalizeCommand(command));
    if (blocked) {
      const alts = checkAlternatives(command);
      process.stderr.write(
        `\n[GateGuard] BLOCKED: ${blocked.message}\n` +
        `  Command: ${command.substring(0, 200)}\n` +
        (alts.length > 0 ? `  Safer alternatives:\n${alts.join('\n')}\n` : '') +
        `  Bypass: GATE_GUARD_BYPASS=1\n\n`
      );
      process.exit(2);
    }

    // 2-7. WARN categories
    const categories = [
      { label: 'WARNING', patterns: WARN_PATTERNS },
      { label: 'PATH', patterns: PATH_WARN },
      { label: 'MODE', patterns: MODE_WARN },
      { label: 'SED', patterns: SED_WARN },
      { label: 'SEMANTIC', patterns: SEMANTIC_WARN },
      { label: 'DESTRUCTIVE_PIPE', patterns: PIPE_DESTRUCTIVE },
    ];

    for (const { label, patterns } of categories) {
      const hit = checkPatterns(patterns, command);
      if (hit) {
        process.stderr.write(`[GateGuard] ${label}: ${hit.message}\n`);
      }
    }

    // Safe alternatives for non-blocking destructive commands
    const alts = checkAlternatives(command);
    for (const a of alts) {
      process.stderr.write(`[GateGuard] SAFE_ALT: ${a}\n`);
    }
  }

  // Sensitive file writes
  const filePath = toolInput.file_path || toolInput.path || toolInput.TargetFile || toolInput.AbsolutePath || toolInput.DirectoryPath || toolInput.uri || '';
  if (filePath && isSensitivePath(filePath)) {
    process.stderr.write(
      `[GateGuard] WARNING: Writing to sensitive file: ${filePath}\n` +
      `  Ensure no secrets are being committed.\n`
    );
  }

  process.exit(0);
});
