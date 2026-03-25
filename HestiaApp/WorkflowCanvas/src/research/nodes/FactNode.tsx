import { Handle, Position, type NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

type FactStatus = 'valid' | 'uncertain' | 'invalidated'

function StatusIndicator({ status }: { status: FactStatus }) {
  if (status === 'valid') {
    return (
      <div style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        backgroundColor: nodeColors.fact.dot,
        flexShrink: 0,
      }} />
    )
  }
  if (status === 'uncertain') {
    return (
      <div style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        border: `1.5px solid ${nodeColors.fact.dot}`,
        backgroundColor: 'transparent',
        flexShrink: 0,
      }} />
    )
  }
  // invalidated — triangle
  return (
    <div style={{
      width: 0,
      height: 0,
      borderLeft: '4px solid transparent',
      borderRight: '4px solid transparent',
      borderBottom: `8px solid #FF6467`,
      flexShrink: 0,
    }} />
  )
}

export function FactNode({ data, selected }: NodeProps) {
  const text = String(data.text ?? data.label ?? 'Fact')
  const confidence = (data.confidence as number) ?? 0.5
  const validAt = data.validAt as string | undefined
  const status = (data.status as FactStatus) ?? 'valid'

  const truncated = text.length > 80 ? text.slice(0, 80) + '...' : text

  return (
    <div style={{
      background: nodeColors.fact.bg,
      border: `1.5px solid ${selected ? nodeColors.fact.dot : nodeColors.fact.border}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 180,
      maxWidth: 260,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: textColors.primary,
      boxShadow: selected ? `0 0 12px ${nodeColors.fact.dot}33` : 'none',
      transition: 'border-color 0.2s ease-out, box-shadow 0.2s ease-out',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: nodeColors.fact.dot }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <StatusIndicator status={status} />
        <span style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.3 }}>
          {truncated}
        </span>
      </div>
      {/* Confidence bar */}
      <div style={{
        height: 3,
        borderRadius: 2,
        background: 'rgba(228,223,215,0.08)',
        marginBottom: 6,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${Math.round(confidence * 100)}%`,
          borderRadius: 2,
          background: `linear-gradient(90deg, ${nodeColors.fact.dot}88, ${nodeColors.fact.dot})`,
          transition: 'width 0.3s ease-out',
        }} />
      </div>
      {validAt && (
        <div style={{ fontSize: 10, color: textColors.faint }}>
          {validAt}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: nodeColors.fact.dot }} />
    </div>
  )
}
