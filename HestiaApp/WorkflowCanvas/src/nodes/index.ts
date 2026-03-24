import type { NodeTypes } from '@xyflow/react'
import { PromptNode } from './PromptNode'
import { ToolNode } from './ToolNode'
import { ConditionNode } from './ConditionNode'
import { ActionNode } from './ActionNode'
import { TriggerNode } from './TriggerNode'
import { DelayNode } from './DelayNode'
export { NODE_COLORS } from './constants'

export const nodeTypes: NodeTypes = {
  run_prompt: PromptNode,
  call_tool: ToolNode,
  if_else: ConditionNode,
  switch: ConditionNode,
  notify: ActionNode,
  log: ActionNode,
  schedule: TriggerNode,
  manual: TriggerNode,
  delay: DelayNode,
}
