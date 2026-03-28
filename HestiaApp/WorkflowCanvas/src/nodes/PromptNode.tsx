import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'

export function PromptNode({ data, selected }: NodeProps) {
  const color = NODE_COLORS.prompt
  const prompt = data.config && typeof data.config === 'object'
    ? (data.config as Record<string, unknown>).prompt as string | undefined
    : undefined
  const truncated = prompt && prompt.length > 60 ? prompt.slice(0, 60) + '…' : prompt

  return (
    <div style={{
      background: '#1a1a2e',
      border: `2px solid ${selected ? color : '#333'}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 160,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: '#E4DFD7',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: color }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span style={{
          fontSize: 10,
          background: color,
          color: '#1a1408',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>PROMPT</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: truncated ? 4 : 0 }}>
        {String(data.label ?? 'Prompt')}
      </div>
      {truncated && (
        <div style={{ fontSize: 11, color: 'rgba(228,223,215,0.55)', lineHeight: 1.4 }}>
          {truncated}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  )
}
