import { useState, useCallback } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

type PrincipleStatus = 'pending' | 'approved' | 'rejected'

function PrincipleStatusIndicator({ status }: { status: PrincipleStatus }) {
  if (status === 'approved') {
    return (
      <div style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        backgroundColor: '#00D492',
        flexShrink: 0,
      }} />
    )
  }
  if (status === 'rejected') {
    return (
      <div style={{
        width: 0,
        height: 0,
        borderLeft: '4px solid transparent',
        borderRight: '4px solid transparent',
        borderBottom: '8px solid #FF6467',
        flexShrink: 0,
      }} />
    )
  }
  // pending — hollow ring with pulse
  return (
    <div style={{
      width: 7,
      height: 7,
      borderRadius: '50%',
      border: `1.5px solid ${nodeColors.principle.dot}`,
      backgroundColor: 'transparent',
      flexShrink: 0,
      animation: 'principle-pulse 2s infinite',
    }} />
  )
}

export function PrincipleNode({ data, selected }: NodeProps) {
  const status = (data.status as PrincipleStatus) ?? 'pending'
  const text = String(data.text ?? data.label ?? '')
  const confidence = (data.confidence as number) ?? 0.5
  const derivedFrom = (data.derivedFrom as string[]) ?? []
  const onApprove = data.onApprove as ((nodeId: string) => void) | undefined
  const onReject = data.onReject as ((nodeId: string) => void) | undefined
  const nodeId = String(data.nodeId ?? '')

  const [editText, setEditText] = useState(text)
  const isPending = status === 'pending'

  const statusLabel = status === 'approved'
    ? 'Approved Principle'
    : status === 'rejected'
      ? 'Rejected Principle'
      : 'Proposed Principle'

  const handleTextChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditText(e.target.value)
  }, [])

  return (
    <div style={{
      background: nodeColors.principle.bg,
      border: `1.5px solid ${selected ? nodeColors.principle.dot : nodeColors.principle.border}`,
      borderRadius: 10,
      padding: '10px 14px',
      minWidth: 200,
      maxWidth: 300,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      color: textColors.primary,
      boxShadow: selected ? `0 0 12px ${nodeColors.principle.dot}33` : 'none',
      transition: 'border-color 0.2s ease-out, box-shadow 0.2s ease-out',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: nodeColors.principle.dot }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <PrincipleStatusIndicator status={status} />
        <span style={{
          fontSize: 10,
          fontWeight: 600,
          color: textColors.secondary,
          letterSpacing: 0.3,
          textTransform: 'uppercase',
        }}>
          {statusLabel}
        </span>
      </div>

      {/* Body — editable when pending */}
      {isPending ? (
        <textarea
          className="nodrag nowheel"
          value={editText}
          onChange={handleTextChange}
          style={{
            width: '100%',
            minHeight: 48,
            background: 'rgba(228,223,215,0.04)',
            border: `1px solid ${nodeColors.principle.border}`,
            borderRadius: 6,
            color: textColors.primary,
            fontSize: 12,
            lineHeight: 1.4,
            padding: '6px 8px',
            resize: 'vertical',
            fontFamily: 'inherit',
            outline: 'none',
            marginBottom: 6,
          }}
          placeholder="Describe this principle..."
        />
      ) : (
        <div style={{
          fontSize: 12,
          lineHeight: 1.4,
          marginBottom: 6,
          color: textColors.primary,
        }}>
          {text}
        </div>
      )}

      {/* Confidence bar — purple to amber */}
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
          background: `linear-gradient(90deg, ${nodeColors.principle.dot}, #E0A050)`,
          transition: 'width 0.3s ease-out',
        }} />
      </div>

      {/* Derived from tags */}
      {derivedFrom.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {derivedFrom.map((source) => (
            <span key={source} style={{
              fontSize: 9,
              background: 'rgba(228,223,215,0.06)',
              color: textColors.faint,
              borderRadius: 8,
              padding: '1px 6px',
            }}>
              {source}
            </span>
          ))}
        </div>
      )}

      {/* Action buttons — pending only */}
      {isPending && onApprove && onReject && (
        <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
          <button
            className="nodrag"
            onClick={() => onApprove(nodeId)}
            style={{
              flex: 1,
              padding: '4px 0',
              fontSize: 11,
              fontWeight: 600,
              background: 'rgba(0,212,146,0.12)',
              color: '#00D492',
              border: '1px solid rgba(0,212,146,0.25)',
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            Approve
          </button>
          <button
            className="nodrag"
            onClick={() => onReject(nodeId)}
            style={{
              flex: 1,
              padding: '4px 0',
              fontSize: 11,
              fontWeight: 600,
              background: 'rgba(255,100,103,0.12)',
              color: '#FF6467',
              border: '1px solid rgba(255,100,103,0.25)',
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            Reject
          </button>
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: nodeColors.principle.dot }} />
    </div>
  )
}
