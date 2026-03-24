import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'
import { darkTheme } from '../theme'

export function ActionNode({ data, selected }: NodeProps) {
  const nodeType = data.nodeType as string | undefined
  const isLog = nodeType === 'log'
  const color = isLog ? darkTheme.nodeType.log : NODE_COLORS.action
  const borderColor = isLog ? 'rgba(235, 223, 209, 0.4)' : color
  const icon = isLog ? '📝' : '🔔'
  const badge = isLog ? 'LOG' : 'NOTIFY'

  return (
    <div style={{
      background: '#1a1a2e',
      border: `2px solid ${selected ? borderColor : '#333'}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 160,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: '#E4DFD7',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: borderColor }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{
          fontSize: 10,
          background: borderColor,
          color: isLog ? '#E4DFD7' : '#1a1408',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>{badge}</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>
        {String(data.label ?? (isLog ? 'Log' : 'Notify'))}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: borderColor }} />
    </div>
  )
}
