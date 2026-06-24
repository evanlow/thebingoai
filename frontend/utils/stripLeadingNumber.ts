/**
 * Strip a leading "1.", "1)", "1:" or "1 " that the LLM sometimes bakes into a
 * briefing section heading, so the component's own counter doesn't render
 * "1. 1) Heading". Auto-imported by Nuxt; used in briefing views + their tests.
 */
export function stripLeadingNumber(heading: string): string {
  return heading.replace(/^\d+[\.\)\:\s]\s*/, '').trim()
}
