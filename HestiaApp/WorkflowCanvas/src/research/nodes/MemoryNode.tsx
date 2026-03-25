import { Handle, Position, type NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

export function MemoryNode({ data, selected }: NodeProps) {
  const content = String(data.content ?? data.label ?? 'Memory')
  const memoryType = String(data.memoryType ?? 'general')
  const importance = (data.importance as number) ?? 0
  const dotColor = nodeColors.memory.dot

  const truncated = content.length > 100
    ? content.slice(0, 100) + '...'
    : content

  return (
    <div style={{
      background: nodeColors.memory.bg,
      border: `1.5px solid ${selected ? dotColor : nodeColors.memory.border}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 180,
      maxWidth: 260,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: textColors.primary,
      boxShadow: selected ? `0 0 12px ${dotColor}33` : 'none',
      transition: 'border-color 0.2s ease-out, box-shadow 0.2s ease-out',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: dotColor }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: dotColor,
          flexShrink: 0,
        }} />
        <span style={{
          fontSize: 10,
          fontWeight: 600,
          color: textColors.secondary,
          letterSpacing: 0.3,
          textTransform: 'uppercase',
        }}>
          Memory
        </span>
      </div>
      <div style={{
        fontSize: 11,
        color: textColors.faint,
        lineHeight: 1.4,
        marginBottom: 8,
      }}>
        {truncated}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          fontSize: 10,
          background: 'rgba(228,223,215,0.06)',
          color: textColors.faint,
          borderRadius: 10,
          padding: '1px 8px',
          fontWeight: 500,
        }}>
          {memoryType}
        </span>
        {importance > 0 && (
          <span style={{ fontSize: 10, color: textColors.faint }}>
            {importance.toFixed(2)}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: dotColor }} />
    </div>
  )
}
