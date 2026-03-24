import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Edge,
  BackgroundVariant,
  type DefaultEdgeOptions,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { bridge } from './bridge'
import { darkTheme } from './theme'

type NodeData = Record<string, unknown>
type CanvasNode = Node<NodeData>
type CanvasEdge = Edge

// CSS overrides for dark theme
const globalStyles = `
  .react-flow__node {
    background: #1a1408;
    border: 1px solid rgba(254, 154, 0, 0.2);
    border-radius: 8px;
    color: #E4DFD7;
    padding: 10px 14px;
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    min-width: 140px;
  }
  .react-flow__node.selected {
    border-color: #E0A050;
    box-shadow: 0 0 0 1px #E0A050;
  }
  .react-flow__node.status-running {
    border-color: #E0A050;
    animation: pulse 1.5s infinite;
  }
  .react-flow__node.status-success {
    border-color: #00D492;
  }
  .react-flow__node.status-failed {
    border-color: #FF6467;
  }
  .react-flow__node.status-skipped {
    opacity: 0.4;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(224, 160, 80, 0.4); }
    50% { box-shadow: 0 0 0 4px rgba(224, 160, 80, 0); }
  }
  .react-flow__edge-path { stroke: rgba(254, 154, 0, 0.3); }
  .react-flow__edge.selected .react-flow__edge-path { stroke: #E0A050; }
  .react-flow__controls { background: #1a1408; border: 1px solid rgba(254, 154, 0, 0.15); border-radius: 8px; }
  .react-flow__controls-button { background: #1a1408; border-bottom: 1px solid rgba(254, 154, 0, 0.1); fill: #E4DFD7; }
  .react-flow__controls-button:hover { background: rgba(238, 203, 160, 0.15); }
  .react-flow__handle { background: #E0A050; width: 8px; height: 8px; }
`

const defaultEdgeOptions: DefaultEdgeOptions = {
  type: 'smoothstep',
  animated: false,
  style: { strokeWidth: 1.5 },
}

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<CanvasEdge>([])

  // Inject global CSS
  useEffect(() => {
    const style = document.createElement('style')
    style.textContent = globalStyles
    document.head.appendChild(style)
    return () => { document.head.removeChild(style) }
  }, [])

  // Register bridge handlers and signal ready
  useEffect(() => {
    bridge.onLoadWorkflow((data) => {
      setNodes(data.nodes.map(n => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: { ...n.data, executionStatus: 'pending' } as NodeData,
      })))
      setEdges(data.edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        label: e.label,
      })))
    })
    bridge.onUpdateNodeStatus((nodeId, status) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, executionStatus: status } }
            : n
        )
      )
    })
    bridge.signalReady()
  }, [setNodes, setEdges])

  // Forward position changes to Swift (debounced in bridge)
  const handleNodesChange = useCallback(
    (changes: NodeChange<CanvasNode>[]) => {
      onNodesChange(changes)
      const moved = changes.filter(
        (c): c is NodeChange & { type: 'position'; position: { x: number; y: number } } =>
          c.type === 'position' && 'position' in c && c.position != null
      )
      if (moved.length > 0) {
        bridge.sendNodesMoved(
          moved.map((c) => ({ id: c.id, x: c.position.x, y: c.position.y }))
        )
      }
    },
    [onNodesChange]
  )

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<CanvasEdge>[]) => {
      onEdgesChange(changes)
      const removed = changes.filter((c) => c.type === 'remove')
      removed.forEach((c) => bridge.sendEdgeDeleted(c.id))
    },
    [onEdgesChange]
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds))
      bridge.sendEdgeCreated({
        source: connection.source,
        target: connection.target,
        sourceHandle: connection.sourceHandle,
      })
    },
    [setEdges]
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    bridge.sendNodeSelected(node.id)
  }, [])

  const onNodesDelete = useCallback((deleted: Node[]) => {
    deleted.forEach((n) => bridge.sendNodeDeleted(n.id))
  }, [])

  // Apply execution status to className for CSS targeting
  const styledNodes = useMemo(
    () => nodes.map((n) => ({
      ...n,
      className: `status-${(n.data?.executionStatus as string) ?? 'pending'}`,
    })),
    [nodes]
  )

  return (
    <div style={{ width: '100vw', height: '100vh', ...darkTheme.container }}>
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodesDelete={onNodesDelete}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        proOptions={{ hideAttribution: true }}
        deleteKeyCode={['Backspace', 'Delete']}
        multiSelectionKeyCode="Meta"
      >
        <Controls showInteractive={false} />
        <MiniMap
          style={darkTheme.minimap}
          nodeColor={() => darkTheme.nodeType.run_prompt}
          maskColor={darkTheme.minimap.maskColor}
        />
        <Background variant={BackgroundVariant.Dots} color={darkTheme.dotColor} gap={20} />
      </ReactFlow>
    </div>
  )
}
