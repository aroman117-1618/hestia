import { darkTheme } from '../theme'

export const NODE_COLORS = {
  prompt: darkTheme.nodeType.run_prompt,
  tool: darkTheme.nodeType.call_tool,
  condition: darkTheme.nodeType.if_else,
  action: darkTheme.nodeType.notify,
  trigger: darkTheme.nodeType.schedule,
  delay: '#8B8B8B',
} as const
