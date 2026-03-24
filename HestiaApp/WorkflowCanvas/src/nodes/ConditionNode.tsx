import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_COLORS } from './constants'

export function ConditionNode({ data, selected }: NodeProps) {
  const color = NODE_COLORS.condition
  const nodeType = data.nodeType as string | undefined
  const isSwitch = nodeType === 'switch'
  const config = data.config && typeof data.config === 'object'
    ? (data.config as Record<string, unknown>)
    : {}
  const cases = isSwitch && Array.isArray(config.cases)
    ? (config.cases as string[])
    : null

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
        <span style={{ fontSize: 16 }}>❓</span>
        <span style={{
          fontSize: 10,
          background: color,
          color: '#1a1408',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 600,
          letterSpacing: 0.3,
        }}>{isSwitch ? 'SWITCH' : 'IF/ELSE'}</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        {String(data.label ?? 'Condition')}
      </div>

      {!isSwitch && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Handle
              type="source"
              position={Position.Bottom}
              id="true"
              style={{ background: '#00D492', left: '25%' }}
            />
            <span style={{ fontSize: 10, color: '#00D492', position: 'absolute', bottom: -18, left: '18%' }}>true</span>
          </div>
          <div style={{ position: 'relative', flex: 1 }}>
            <Handle
              type="source"
              position={Position.Bottom}
              id="false"
              style={{ background: '#FF6467', left: '75%' }}
            />
            <span style={{ fontSize: 10, color: '#FF6467', position: 'absolute', bottom: -18, left: '68%' }}>false</span>
          </div>
        </div>
      )}

      {isSwitch && cases && cases.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 4 }}>
          {cases.map((c, i) => (
            <div key={c} style={{ position: 'relative', textAlign: 'center' }}>
              <Handle
                type="source"
                position={Position.Bottom}
                id={c}
                style={{ background: color, left: `${(i / (cases.length - 1 || 1)) * 100}%` }}
              />
              <span style={{ fontSize: 9, color: 'rgba(228,223,215,0.6)', position: 'absolute', bottom: -16, whiteSpace: 'nowrap', transform: 'translateX(-50%)' }}>
                {c}
              </span>
            </div>
          ))}
        </div>
      )}

      {!cases && isSwitch && (
        <Handle type="source" position={Position.Bottom} style={{ background: color }} />
      )}

      {!isSwitch && null}
    </div>
  )
}
