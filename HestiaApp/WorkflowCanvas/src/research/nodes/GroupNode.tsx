import { useState, useCallback } from 'react'
import type { NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

export function GroupNode({ data }: NodeProps) {
  const initialLabel = String(data.label ?? 'Group')
  const onLabelChange = data.onLabelChange as ((id: string, label: string) => void) | undefined
  const nodeId = String(data.nodeId ?? '')

  const [label, setLabel] = useState(initialLabel)
  const [collapsed, setCollapsed] = useState(false)

  const handleLabelChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLabel(e.target.value)
    onLabelChange?.(nodeId, e.target.value)
  }, [nodeId, onLabelChange])

  const toggleCollapse = useCallback(() => {
    setCollapsed(prev => !prev)
  }, [])

  return (
    <div style={{
      background: nodeColors.group.bg,
      border: `1.5px dashed ${nodeColors.group.border}`,
      borderRadius: 12,
      minWidth: collapsed ? 180 : 300,
      minHeight: collapsed ? 40 : 200,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      transition: 'min-height 0.3s ease-out, min-width 0.3s ease-out',
      overflow: 'visible',
    }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 12px',
          cursor: 'pointer',
          userSelect: 'none',
          borderBottom: collapsed ? 'none' : `1px dashed ${nodeColors.group.border}`,
        }}
        onClick={toggleCollapse}
      >
        <span style={{
          fontSize: 10,
          color: textColors.faint,
          transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease-out',
          display: 'inline-block',
        }}>
          ▼
        </span>
        <input
          className="nodrag"
          value={label}
          onChange={handleLabelChange}
          onClick={(e) => e.stopPropagation()}
          style={{
            background: 'transparent',
            border: 'none',
            color: textColors.secondary,
            fontSize: 12,
            fontWeight: 600,
            outline: 'none',
            padding: 0,
            fontFamily: 'inherit',
            flex: 1,
          }}
        />
      </div>
      {/* Child content area — React Flow renders children inside via extent: 'parent' */}
      {!collapsed && (
        <div style={{
          padding: 8,
          minHeight: 160,
        }} />
      )}
    </div>
  )
}
