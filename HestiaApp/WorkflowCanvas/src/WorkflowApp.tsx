import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type Connection,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Edge,
  type EdgeProps,
  BackgroundVariant,
  type DefaultEdgeOptions,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { createBridge, initBridgeGlobals } from './shared/bridge'
import { darkTheme } from './shared/theme'
import { nodeTypes } from './nodes'
import { AddStepMenu } from './components/AddStepMenu'

const bridge = createBridge('workflow')
initBridgeGlobals(bridge)

type NodeData = Record<string, unknown>
type CanvasNode = Node<NodeData>
type CanvasEdge = Edge

// CSS overrides for dark theme
const globalStyles = `
  .react-flow__node {
    background: transparent;
    border: none;
    padding: 0;
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .react-flow__node.status-running {
    animation: pulse-glow 1.5s infinite;
  }
  .react-flow__node.status-success > div {
    border-color: #00D492 !important;
  }
  .react-flow__node.status-failed > div {
    border-color: #FF6467 !important;
  }
  .react-flow__node.status-skipped {
    opacity: 0.4;
  }
  @keyframes pulse-glow {
    0%, 100% { filter: drop-shadow(0 0 0px rgba(224, 160, 80, 0)); }
    50% { filter: drop-shadow(0 0 6px rgba(224, 160, 80, 0.5)); }
  }
  .react-flow__edge-path { stroke: rgba(254, 154, 0, 0.3); }
  .react-flow__edge.selected .react-flow__edge-path { stroke: #E0A050; }
  .react-flow__controls { background: #1a1408; border: 1px solid rgba(254, 154, 0, 0.15); border-radius: 8px; }
  .react-flow__controls-button { background: #1a1408; border-bottom: 1px solid rgba(254, 154, 0, 0.1); fill: #E4DFD7; }
  .react-flow__controls-button:hover { background: rgba(238, 203, 160, 0.15); }
  .react-flow__handle {
    width: 10px;
    height: 10px;
    z-index: 10;
    cursor: crosshair;
  }
  .react-flow__handle:hover {
    width: 14px;
    height: 14px;
    transition: width 0.15s, height 0.15s;
  }
`

const defaultEdgeOptions: DefaultEdgeOptions = {
  type: 'default',
  animated: false,
  style: { strokeWidth: 1.5 },
}

interface AddMenuState {
  x: number
  y: number
  canvasX: number
  canvasY: number
  afterNodeId?: string
}

export default function WorkflowApp() {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<CanvasEdge>([])
  const [addMenu, setAddMenu] = useState<AddMenuState | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfInstance = useRef<any>(null)

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
        data: {
          label: n.data.label,
          nodeType: n.data.nodeType ?? n.type,
          config: n.data.config ?? {},
          executionStatus: 'pending',
        } as NodeData,
      })))
      setEdges(data.edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        label: e.label,
      })))
      // Fit viewport to nodes after data loads (delay to let React render)
      setTimeout(() => {
        rfInstance.current?.fitView({ padding: 0.2 })
      }, 100)
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

  const onPaneContextMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    e.preventDefault()
    const clientX = 'clientX' in e ? e.clientX : 0
    const clientY = 'clientY' in e ? e.clientY : 0
    setAddMenu({
      x: clientX,
      y: clientY,
      canvasX: clientX,
      canvasY: clientY,
      afterNodeId: undefined,
    })
  }, [])

  const handleAddStepSelect = useCallback((stepType: string) => {
    if (!addMenu) return
    bridge.sendAddStep({
      title: stepType.charAt(0).toUpperCase() + stepType.slice(1),
      stepType,
      positionX: addMenu.canvasX,
      positionY: addMenu.canvasY,
      afterNodeId: addMenu.afterNodeId,
    })
    setAddMenu(null)
  }, [addMenu])

  // AddButtonEdge defined inside App to capture setAddMenu via closure
  function AddButtonEdge(props: EdgeProps) {
    const [edgePath, labelX, labelY] = getSmoothStepPath({
      sourceX: props.sourceX,
      sourceY: props.sourceY,
      targetX: props.targetX,
      targetY: props.targetY,
    })
    return (
      <>
        <BaseEdge path={edgePath} style={props.style} markerEnd={props.markerEnd} />
        <EdgeLabelRenderer>
          <button
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              width: 20,
              height: 20,
              borderRadius: '50%',
              background: '#333',
              border: '1px solid #555',
              color: '#aaa',
              fontSize: 14,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'all',
              lineHeight: 1,
              padding: 0,
            }}
            className="nodrag nopan"
            onClick={(e) => {
              e.stopPropagation()
              setAddMenu({
                x: e.clientX,
                y: e.clientY,
                canvasX: labelX,
                canvasY: labelY,
                afterNodeId: props.source,
              })
            }}
          >
            +
          </button>
        </EdgeLabelRenderer>
      </>
    )
  }

  const edgeTypes = useMemo(() => ({ default: AddButtonEdge }), [])

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
        onPaneContextMenu={onPaneContextMenu}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        onInit={(instance) => { rfInstance.current = instance }}
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
      {addMenu && (
        <AddStepMenu
          x={addMenu.x}
          y={addMenu.y}
          onSelect={handleAddStepSelect}
          onClose={() => setAddMenu(null)}
        />
      )}
    </div>
  )
}
