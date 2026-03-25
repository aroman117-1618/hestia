import { Handle, Position, type NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: '#4A9EFF',
  organization: '#E0A050',
  concept: '#8050C8',
  place: '#00D492',
  event: '#FFB900',
  default: '#4A9EFF',
}

export function EntityNode({ data, selected }: NodeProps) {
  const name = String(data.name ?? data.label ?? 'Entity')
  const summary = data.summary as string | undefined
  const entityType = String(data.entityType ?? 'default')
  const connections = (data.connections as number) ?? 0
  const dotColor = ENTITY_TYPE_COLORS[entityType] ?? ENTITY_TYPE_COLORS.default

  const truncatedSummary = summary && summary.length > 80
    ? summary.slice(0, 80) + '...'
    : summary

  return (
    <div style={{
      background: nodeColors.entity.bg,
      border: `1.5px solid ${selected ? dotColor : nodeColors.entity.border}`,
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
        <span style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.3 }}>
          {name}
        </span>
      </div>
      {truncatedSummary && (
        <div style={{
          fontSize: 11,
          color: textColors.faint,
          lineHeight: 1.4,
          marginBottom: 8,
        }}>
          {truncatedSummary}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          fontSize: 10,
          background: `${dotColor}22`,
          color: dotColor,
          borderRadius: 10,
          padding: '1px 8px',
          fontWeight: 500,
        }}>
          {entityType}
        </span>
        {connections > 0 && (
          <span style={{ fontSize: 10, color: textColors.faint }}>
            {connections} link{connections !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: dotColor }} />
    </div>
  )
}
