/**
 * Pure policy classification. Keeping this module independent from Cordis lets
 * deployments test their configured rules without booting an agent or shell.
 *
 * DESTRUCTIVE_PATTERNS mirrors the harness guard's named pattern list
 * (`.claude/hooks/guard.py` in g-harness, the 41-pattern set from the guard
 * hardening). The two lists are maintained together: when the guard gains a
 * pattern, add the same id here and a sample in `test/rules.test.mjs`, or the
 * `every destructive pattern has a sample` test fails. Ids are the guard's ids,
 * so a diff between the two lists is mechanical.
 */

const DESTRUCTIVE_COMMAND = /(?:^|[;&|\n])\s*(?:rm\s+-[^\n]*r|del\s+\/|Remove-Item\b|git\s+(?:reset\s+--hard|clean\b|push\s+--force(?:-with-lease)?\b)|drop\s+(?:database|table)\b)/i
const PRIVILEGE_COMMAND = /(?:^|[;&|\n])\s*(?:sudo\b|runas\b|chmod\s+777\b)/i
const DEPENDENCY_COMMAND = /(?:^|[;&|\n])\s*(?:npm|pnpm|yarn|pip|pip3|uv|cargo)\s+(?:install|add|remove|uninstall)\b/i
const NETWORK_COMMAND = /(?:^|[;&|\n])\s*(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod)\b/i
const SECRET_ASSIGNMENT = /(\b(?:api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*["']?)([^\s"']{12,})/ig
const PROTECTED_PATH = /(?:^|[\\/])(?:\.env(?:\.[^\\/]+)?|[^\\/]+\.(?:pem|key|p12|pfx))$/i

/** @typedef {'allow'|'ask'|'deny'} PolicyAction */

/**
 * Named destructive patterns, ids taken from the harness guard. Anything matched
 * here needs explicit approval, because the harness would refuse it too.
 * @type {ReadonlyArray<{id: string, re: RegExp}>}
 */
export const DESTRUCTIVE_PATTERNS = Object.freeze([
  { id: 'rm_root', re: /rm\s+-[^\n]*(?:\s|^)\/(?:\s|$|\*)/ },
  { id: 'rm_home', re: /rm\s+-[^\n]*~/ },
  { id: 'rm_wildcard', re: /rm\s+-[^\n]*\*/ },
  { id: 'rm_relative_wildcard', re: /rm\s+-[^\n]*\.\/(?:\s|$|\*)/ },
  { id: 'rm_system_dir', re: /rm\s+-[^\n]*\/(?:etc|usr|var|bin|lib|boot|sbin|opt|sys|proc|dev)(?:\/|\s|$)/ },
  { id: 'rm_temp_linux', re: /rm\s+-[^\n]*\/tmp\// },
  { id: 'rm_temp_win', re: /rm\s+-[^\n]*\$?(?:env:)?TEMP\b/i },
  { id: 'rm_after_other_target', re: /rm\b[^\n]*;_?[^\n]*\srm\b/ },
  { id: 'force_push_main', re: /git\s+push\b[^&|;\n]*(?:--force|-f)\s+[^&|;\n]*(?:main|master)/ },
  { id: 'force_push_any', re: /git\s+push\b[^&|;\n]*--force\b(?!-)/ },
  { id: 'force_push_refspec', re: /git\s+push\b[^&|;\n]*\s\+[^\s&|;]+/ },
  { id: 'force_push_delete_main', re: /git\s+push\b[^&|;\n]*(?:--delete\s+|-d\s+|:)(?:[^\s&|;]+\s+)?(?:refs\/heads\/)?(?:main|master)(?![\w-])/ },
  { id: 'git_reset_hard', re: /git\s+reset\b[^&|;\n]*--ha(?:rd?)?/ },
  { id: 'git_clean_force', re: /git\s+clean\s+-f/ },
  { id: 'drop_table', re: /DROP\s+(?:TABLE|DATABASE)/i },
  { id: 'truncate_table', re: /TRUNCATE\s+TABLE/i },
  { id: 'dd_device_write', re: /dd\s+.*of=\/dev\// },
  { id: 'dd_raw', re: /dd\s+if=/ },
  { id: 'dev_write', re: />\s*\/dev\/(?:sd|hd|nvme|vd)/ },
  { id: 'mkfs', re: /mkfs\./ },
  { id: 'shred', re: /shred\s+/ },
  { id: 'chmod_chown_system', re: /(?:chmod|chown)\s+-R\s+(?:[^/\s]+\s+)*\/(?:etc|usr|var|bin|lib|boot|sbin|opt|root|sys|proc|dev)(?:\/|\s|$)/ },
  { id: 'win_del_force', re: /del\s+/i },
  { id: 'win_rd_recursive', re: /(?:rd|rmdir)\s+(?:.*\s)?\/s\b/i },
  { id: 'win_remove_recursive', re: /Remove-Item\s+.*-Recurse.*-Force/i },
  { id: 'win_format_volume', re: /(?:^|[;&|]\s*)Format-Volume\b/i },
  { id: 'win_clear_disk', re: /(?:^|[;&|]\s*)clear-disk\b/i },
  { id: 'win_reg_delete', re: /(?:^|[;&|]\s*)reg(?:\.exe)?\s+delete\b/i },
  { id: 'win_vssadmin_delete', re: /vssadmin\s+delete\b/i },
  { id: 'win_stop_computer', re: /(?:^|[;&|]\s*)Stop-Computer\b/i },
  { id: 'win_restart_computer', re: /(?:^|[;&|]\s*)Restart-Computer\b/i },
  { id: 'format_disk', re: /(?:^|[;&|]\s*)format\s+(?:\/\S+\s+)*[a-zA-Z]:/i },
  { id: 'diskpart', re: /(?:^|[;&|]\s*)diskpart\b/i },
  { id: 'shutdown_system', re: /(?:^|[;&|]\s*)(?:shutdown|reboot|halt)\b/i },
  { id: 'curl_pipe_shell', re: /(?:^|[;&|]\s*)(?:curl|wget)\s+[^|&;\n]*\|\s*(?:(?:sudo|env)\s+)?(?:(?:ba|z|k)?sh\b|python[0-9.]*\b|perl\b|ruby\b|node\b|pwsh\b|powershell\b|iex\b)/i },
  { id: 'powershell_download_pipe_iex', re: /(?:^|[;&|]\s*)(?:irm|iwr|Invoke-WebRequest|Invoke-RestMethod)\b[^|&;\n]*\|\s*(?:iex|Invoke-Expression)\b/i },
])

/**
 * Return a deterministic decision for a shell command under the balanced
 * preset. The caller can make the final approval decision through DSH's
 * approval seam.
 * @param {string} command
 * @returns {{action: PolicyAction, reason?: string}}
 */
export function classifyCommand(command) {
  const matched = DESTRUCTIVE_PATTERNS.find((pattern) => pattern.re.test(command))
  if (matched !== undefined) {
    return { action: 'ask', reason: `destructive command requires approval (${matched.id})` }
  }
  if (DESTRUCTIVE_COMMAND.test(command)) return { action: 'ask', reason: 'destructive command requires approval' }
  if (PRIVILEGE_COMMAND.test(command)) return { action: 'ask', reason: 'privileged command requires approval' }
  if (DEPENDENCY_COMMAND.test(command)) return { action: 'ask', reason: 'dependency changes require approval' }
  if (NETWORK_COMMAND.test(command)) return { action: 'ask', reason: 'network command requires approval' }
  return { action: 'allow' }
}

/**
 * Classify a model-facing tool invocation from its stable name and arguments.
 * @param {string} name
 * @param {unknown} args
 * @returns {{action: PolicyAction, reason?: string}}
 */
export function classifyTool(name, args) {
  const record = args !== null && typeof args === 'object' ? args : {}
  const path = typeof record.path === 'string' ? record.path : undefined
  if (path && PROTECTED_PATH.test(path)) return { action: 'deny', reason: 'protected credential file cannot be changed by an agent' }
  if (/^(?:write|edit|apply_patch|bash|powershell|terminal)$/i.test(name)) {
    const command = typeof record.command === 'string' ? record.command : typeof record.script === 'string' ? record.script : undefined
    if (command !== undefined) return classifyCommand(command)
    return { action: 'ask', reason: 'file changes require approval in balanced mode' }
  }
  if (/^(?:git_commit|git_push)$/i.test(name)) return { action: 'ask', reason: 'git publication requires approval' }
  return { action: 'allow' }
}

/** Replace likely credential values before they are placed in an audit record. */
export function redactSecrets(text) {
  return text.replace(SECRET_ASSIGNMENT, '$1[REDACTED]')
}
