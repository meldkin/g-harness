import { classifyTool } from './rules.js'

export const name = 'solo-policy'
export const inject = ['tools']

/**
 * Apply the balanced policy through DSH's approval seam. This plugin does not
 * execute commands or replace the sandbox; it only decides allow, ask, deny.
 * @param {import('@deepseek-ai/cordis').Context} ctx
 */
export function apply(ctx) {
  ctx.on('tools/pre-execute', async (exec, next) => {
    const decision = classifyTool(exec.name, exec.arguments)
    if (decision.action === 'deny') return { kind: 'deny', reason: decision.reason }
    if (decision.action === 'ask') return { kind: 'ask', reason: decision.reason }
    return next()
  })
}

export default { name, inject, apply }
