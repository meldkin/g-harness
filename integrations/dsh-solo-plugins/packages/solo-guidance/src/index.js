export const name = 'solo-guidance'
export const inject = ['skills']

const skills = [
  ['solo-plan', 'Plan multi-file changes before editing.', 'For a complex request, identify scope, risks, tests, and approval points before implementation.'],
  ['solo-debug', 'Investigate failures with competing hypotheses.', 'State at least two plausible causes, gather evidence for each, then make the smallest verified fix.'],
  ['solo-review', 'Review a diff for correctness and security.', 'Report findings by severity with file locations and evidence. Do not modify files during a review.'],
  ['solo-verify', 'Verify code changes with relevant tests and scans.', 'Run focused tests first, then report exact commands, exit codes, and remaining risks.'],
]

/** @param {import('@deepseek-ai/cordis').Context} ctx */
export function apply(ctx) {
  for (const [skillName, description, content] of skills) {
    ctx.effect(() => ctx.skills.register({
      name: skillName,
      description,
      content,
      source: 'bundled',
      locator: `solo-guidance:${skillName}`,
    }))
  }
}

export default { name, inject, apply }
