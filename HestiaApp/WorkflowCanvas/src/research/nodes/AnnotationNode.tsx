import { useState, useCallback } from 'react'
import type { NodeProps } from '@xyflow/react'
import { nodeColors, textColors } from '../../shared/theme'

export function AnnotationNode({ data }: NodeProps) {
  const initialText = String(data.text ?? '')
  const onTextChange = data.onTextChange as ((id: string, text: string) => void) | undefined
  const onDelete = data.onDelete as ((id: string) => void) | undefined
  const nodeId = String(data.nodeId ?? '')

  const [text, setText] = useState(initialText)
  const [hovered, setHovered] = useState(false)

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    onTextChange?.(nodeId, e.target.value)
  }, [nodeId, onTextChange])

  const handleDelete = useCallback(() => {
    onDelete?.(nodeId)
  }, [nodeId, onDelete])

  return (
    <div
      style={{
        background: nodeColors.annotation.bg,
        border: `1px dashed ${nodeColors.annotation.border}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 160,
        maxWidth: 280,
        fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
        position: 'relative',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Delete button — visible on hover */}
      {hovered && (
        <button
          className="nodrag"
          onClick={handleDelete}
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: 'rgba(255,100,103,0.15)',
            color: '#FF6467',
            border: 'none',
            cursor: 'pointer',
            fontSize: 11,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
            padding: 0,
            fontFamily: 'inherit',
          }}
        >
          x
        </button>
      )}

      <textarea
        className="nodrag nowheel"
        value={text}
        onChange={handleChange}
        placeholder="Add a note..."
        style={{
          width: '100%',
          minHeight: 40,
          background: 'transparent',
          border: 'none',
          color: textColors.secondary,
          fontSize: 12,
          lineHeight: 1.4,
          resize: 'vertical',
          fontFamily: 'inherit',
          outline: 'none',
          padding: 0,
        }}
      />
      {/* No handles — annotations don't connect */}
    </div>
  )
}
