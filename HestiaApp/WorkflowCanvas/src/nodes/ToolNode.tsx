import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'

export function ToolNode({ data, selected }: NodeProps) {
  const color = NODE_COLORS.tool
  const config = data.config && typeof data.config === 'object'
    ? (data.config as Record<string, unknown>)
    : {}
  const toolName = config.tool_name as string | undefined

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
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
        <span style={{
          fontSize: 10,
          background: color,
          color: '#fff',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>TOOL</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: toolName ? 4 : 0 }}>
        {String(data.label ?? 'Tool Call')}
      </div>
      {toolName && (
        <div style={{ fontSize: 11, color: 'rgba(74,158,255,0.8)', fontFamily: 'monospace' }}>
          {toolName}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  )
}
