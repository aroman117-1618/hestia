import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

export function DelayNode({ data, selected }: NodeProps) {
  const color = NODE_COLORS.delay
  const config = data.config && typeof data.config === 'object'
    ? (data.config as Record<string, unknown>)
    : {}
  const delaySeconds = typeof config.delay_seconds === 'number' ? config.delay_seconds : null

  return (
    <div style={{
      background: '#1a1a2e',
      border: `2px solid ${selected ? color : '#333'}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 140,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: '#E4DFD7',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: color }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 8 14"/></svg>
        <span style={{
          fontSize: 10,
          background: color,
          color: '#fff',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>DELAY</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: delaySeconds !== null ? 2 : 0 }}>
        {String(data.label ?? 'Delay')}
      </div>
      {delaySeconds !== null && (
        <div style={{ fontSize: 12, color: 'rgba(228,223,215,0.6)' }}>
          Wait {formatDuration(delaySeconds)}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  )
}
