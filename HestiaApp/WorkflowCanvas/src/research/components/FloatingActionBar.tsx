import { textColors, nodeColors } from '../../shared/theme'

interface FloatingActionBarProps {
  selectedCount: number
  position: { x: number; y: number }
  onDistill: () => void
  onGroup: () => void
  onRemove: () => void
}

export function FloatingActionBar({
  selectedCount,
  position,
  onDistill,
  onGroup,
  onRemove,
}: FloatingActionBarProps) {
  return (
    <div style={{
      position: 'absolute',
      left: position.x,
      top: position.y,
      transform: 'translate(-50%, -100%) translateY(-12px)',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'rgba(20,14,6,0.92)',
      border: '1px solid rgba(228,223,215,0.1)',
      borderRadius: 10,
      padding: '6px 10px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      zIndex: 1000,
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      pointerEvents: 'all',
    }}>
      <button
        onClick={onDistill}
        style={{
          padding: '4px 12px',
          fontSize: 11,
          fontWeight: 600,
          background: `${nodeColors.principle.dot}1A`,
          color: nodeColors.principle.dot,
          border: `1px solid ${nodeColors.principle.dot}33`,
          borderRadius: 6,
          cursor: 'pointer',
          fontFamily: 'inherit',
          whiteSpace: 'nowrap',
        }}
      >
        Distill Principle
      </button>
      <button
        onClick={onGroup}
        style={{
          padding: '4px 12px',
          fontSize: 11,
          fontWeight: 600,
          background: 'rgba(228,223,215,0.06)',
          color: textColors.secondary,
          border: '1px solid rgba(228,223,215,0.1)',
          borderRadius: 6,
          cursor: 'pointer',
          fontFamily: 'inherit',
          whiteSpace: 'nowrap',
        }}
      >
        Group
      </button>
      <button
        onClick={onRemove}
        style={{
          padding: '4px 12px',
          fontSize: 11,
          fontWeight: 600,
          background: 'rgba(255,100,103,0.08)',
          color: 'rgba(255,100,103,0.7)',
          border: '1px solid rgba(255,100,103,0.15)',
          borderRadius: 6,
          cursor: 'pointer',
          fontFamily: 'inherit',
          whiteSpace: 'nowrap',
        }}
      >
        Remove
      </button>
      <span style={{
        fontSize: 10,
        color: textColors.faint,
        marginLeft: 4,
        whiteSpace: 'nowrap',
      }}>
        {selectedCount} sel
      </span>
    </div>
  )
}
