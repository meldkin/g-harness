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
 * Secret shapes the redactor must recognise, ids taken verbatim from the harness
 * guard's list so a diff between the two is mechanical. Token shapes replace the
 * whole match; assignment shapes keep the key name (via `$1`) because an audit
 * record is more useful when it says which secret leaked. URL shapes keep the
 * scheme and host and drop only the userinfo.
 * @type {ReadonlyArray<{id: string, re: RegExp, replacement?: string | ((match: string) => string)}>}
 */
export const SECRET_PATTERNS = Object.freeze([
  { id: 'aws_access_key', re: /(?:AKIA|ASIA)[A-Z0-9]{16}/g },
  { id: 'google_api_key', re: /AIza[0-9A-Za-z_-]{35}/g },
  { id: 'anthropic_key', re: /sk-ant-[A-Za-z0-9\-_]{24,}/g },
  { id: 'openai_project_key', re: /sk-proj-[A-Za-z0-9\-_]{20,}/g },
  { id: 'openai_legacy_key', re: /sk-[A-Za-z0-9]{20,}/g },
  { id: 'stripe_key', re: /(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}/g },
  { id: 'npm_token', re: /npm_[A-Za-z0-9]{36}/g },
  { id: 'gitlab_pat', re: /glpat-[A-Za-z0-9\-_]{20,}/g },
  { id: 'digitalocean_token', re: /dop_v1_[A-Za-z0-9]{64}/g },
  { id: 'github_token', re: /(?:gh[pousr]_|github[_-]?pat[_-]?|github[_-]?token[_-]?)[A-Za-z0-9_]{20,}/gi },
  { id: 'slack_token', re: /xox[baprs]-[0-9A-Za-z-]{10,}/g },
  { id: 'jwt_token', re: /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g },
  { id: 'private_key_pem', re: /-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/g },
  { id: 'discord_webhook', re: /https:\/\/discord(?:app)?\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+/gi },
  { id: 'bearer_header', re: /Bearer\s+[A-Za-z0-9._\-+/=]{20,}/gi },
  { id: 'basic_auth', re: /https?:\/\/[^:@/\s]+:[^@/\s]+@/gi, replacement: (match) => match.replace(/\/\/.*@/, '//[REDACTED]@') },
  { id: 'mongodb_uri', re: /mongodb(?:\+srv)?:\/\/[^:@/\s]+:[^@/\s]+@/gi, replacement: (match) => match.replace(/\/\/.*@/, '//[REDACTED]@') },
  { id: 'postgres_uri', re: /postgres(?:ql)?:\/\/[^:@/\s]+:[^@/\s]+@/gi, replacement: (match) => match.replace(/\/\/.*@/, '//[REDACTED]@') },
  { id: 'redis_uri', re: /redis:\/\/[^:@/\s]+:[^@/\s]+@/gi, replacement: (match) => match.replace(/\/\/.*@/, '//[REDACTED]@') },
  { id: 'aws_secret_key', re: /((?:aws|amazon).{0,20}(?:secret|key|token).{0,10}[:=]\s*["'])[A-Za-z0-9/+=]{20,}/gi, replacement: '$1[REDACTED]' },
  { id: 'generic_api_key', re: /((?:api[_-]?key|apikey|secret|password)\s*[:=]\s*["'])(?!\$)[^"']{8,}/gi, replacement: '$1[REDACTED]' },
  { id: 'hardcoded_token', re: /((?:token|bearer)\s*[:=]\s*["'])[A-Za-z0-9._\-+/=]{20,}/gi, replacement: '$1[REDACTED]' },
  { id: 'env_assignment_secret', re: /((?:api[_-]?key|secret|token|password|passwd|credential)[a-z_-]*\s*[:=]\s*)(?![^\s"']*(?:x{3}|\*{3}))[^\s"'$][^\s"']{15,}/gi, replacement: '$1[REDACTED]' },
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
  let redacted = text
  for (const pattern of SECRET_PATTERNS) {
    // String.prototype.replace takes a string (with $1) or a function, so the
    // per-pattern replacement needs no branching here.
    redacted = redacted.replace(pattern.re, pattern.replacement ?? '[REDACTED]')
  }
  // The legacy assignment rule stays last: it is the broadest of the family and
  // catches short values the specific patterns above deliberately ignore.
  return redacted.replace(SECRET_ASSIGNMENT, '$1[REDACTED]')
}
