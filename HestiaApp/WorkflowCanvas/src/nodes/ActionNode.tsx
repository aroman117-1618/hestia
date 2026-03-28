import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'
import { darkTheme } from '../shared/theme'

export function ActionNode({ data, selected }: NodeProps) {
  const nodeType = data.nodeType as string | undefined
  const isLog = nodeType === 'log'
  const color = isLog ? darkTheme.nodeType.log : NODE_COLORS.action
  const borderColor = isLog ? 'rgba(235, 223, 209, 0.4)' : color
  const badge = isLog ? 'LOG' : 'NOTIFY'
  const icon = isLog
    ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
    : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>

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
        {icon}
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
