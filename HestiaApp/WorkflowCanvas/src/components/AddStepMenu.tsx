import { NODE_COLORS } from '../nodes/constants'

const STEP_TYPES = [
  { type: 'prompt', label: 'Prompt Step', icon: '💬', desc: 'Send a prompt to the LLM', color: NODE_COLORS.prompt },
  { type: 'notify', label: 'Notification', icon: '🔔', desc: 'Send a notification', color: NODE_COLORS.action },
  { type: 'condition', label: 'Condition', icon: '❓', desc: 'Branch based on a condition', color: NODE_COLORS.condition },
  { type: 'tool', label: 'Tool Call', icon: '🔧', desc: 'Execute a tool directly', color: NODE_COLORS.tool },
  { type: 'delay', label: 'Delay', icon: '⏳', desc: 'Wait before continuing', color: NODE_COLORS.delay },
]

interface AddStepMenuProps {
  x: number
  y: number
  onSelect: (stepType: string) => void
  onClose: () => void
}

export function AddStepMenu({ x, y, onSelect, onClose }: AddStepMenuProps) {
  return (
    <>
      {/* Transparent backdrop */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 999,
        }}
        onClick={onClose}
      />
      {/* Menu popup */}
      <div
        style={{
          position: 'fixed',
          left: x,
          top: y,
          zIndex: 1000,
          background: '#1a1a2e',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          padding: '6px',
          minWidth: 220,
          fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
        }}
      >
        <div style={{
          fontSize: 10,
          color: 'rgba(228,223,215,0.4)',
          letterSpacing: 0.8,
          fontWeight: 600,
          padding: '4px 8px 6px',
          textTransform: 'uppercase',
        }}>
          Add Step
        </div>
        {STEP_TYPES.map((step) => (
          <button
            key={step.type}
            onClick={() => onSelect(step.type)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: '100%',
              background: 'transparent',
              border: 'none',
              borderRadius: 7,
              padding: '7px 10px',
              cursor: 'pointer',
              textAlign: 'left',
              color: '#E4DFD7',
              transition: 'background 0.12s',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.07)'
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
            }}
          >
            <span style={{
              fontSize: 18,
              width: 28,
              textAlign: 'center',
              flexShrink: 0,
            }}>{step.icon}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: step.color }}>
                {step.label}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(228,223,215,0.5)', marginTop: 1 }}>
                {step.desc}
              </div>
            </div>
          </button>
        ))}
      </div>
    </>
  )
}
