import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'

export function TriggerNode({ data, selected }: NodeProps) {
  const color = NODE_COLORS.trigger
  const nodeType = data.nodeType as string | undefined
  const isManual = nodeType === 'manual'
  const badge = isManual ? 'MANUAL' : 'SCHEDULE'
  const icon = isManual
    ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5,3 19,12 5,21"/></svg>
    : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {icon}
        <span style={{
          fontSize: 10,
          background: color,
          color: '#fff',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>{badge}</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>
        {String(data.label ?? (isManual ? 'Manual Trigger' : 'Schedule'))}
      </div>
      {/* Trigger nodes have no incoming handle — they start the flow */}
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  )
}
