import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  type Connection,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Edge,
  type OnSelectionChangeParams,
  BackgroundVariant,
  type DefaultEdgeOptions,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { createBridge, initBridgeGlobals } from '../shared/bridge'
import { darkTheme, nodeColors, textColors } from '../shared/theme'
import { EntityNode } from './nodes/EntityNode'
import { FactNode } from './nodes/FactNode'
import { PrincipleNode } from './nodes/PrincipleNode'
import { MemoryNode } from './nodes/MemoryNode'
import { AnnotationNode } from './nodes/AnnotationNode'
import { GroupNode } from './nodes/GroupNode'
import { FloatingActionBar } from './components/FloatingActionBar'

const bridge = createBridge('research')
initBridgeGlobals(bridge)

// Register node types OUTSIDE component (React Flow performance requirement)
const researchNodeTypes = {
  entity: EntityNode,
  fact: FactNode,
  principle: PrincipleNode,
  memory: MemoryNode,
  annotation: AnnotationNode,
  group: GroupNode,
}

type NodeData = Record<string, unknown>
type CanvasNode = Node<NodeData>
type CanvasEdge = Edge

// CSS overrides for research dark theme
const globalStyles = `
  .react-flow__node {
    background: transparent;
    border: none;
    padding: 0;
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .react-flow__node.selected > div {
    /* handled inline via selected prop */
  }
  .react-flow__edge-path { stroke: rgba(228,223,215,0.12); }
  .react-flow__edge.selected .react-flow__edge-path { stroke: rgba(228,223,215,0.4); }
  .react-flow__controls { background: #110B03; border: 1px solid rgba(228,223,215,0.08); border-radius: 8px; }
  .react-flow__controls-button { background: #110B03; border-bottom: 1px solid rgba(228,223,215,0.06); fill: ${textColors.primary}; }
  .react-flow__controls-button:hover { background: rgba(228,223,215,0.06); }
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
  .react-flow__selection {
    background: rgba(128,80,200,0.08) !important;
    border: 1px solid rgba(128,80,200,0.25) !important;
  }
  @keyframes principle-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
`

const defaultEdgeOptions: DefaultEdgeOptions = {
  type: 'default',
  animated: false,
  style: { strokeWidth: 1.2 },
}

function ResearchCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<CanvasEdge>([])
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([])
  const [selectionCenter, setSelectionCenter] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const { screenToFlowPosition } = useReactFlow()

  // Inject global CSS
  useEffect(() => {
    const style = document.createElement('style')
    style.textContent = globalStyles
    document.head.appendChild(style)
    return () => { document.head.removeChild(style) }
  }, [])

  // Principle approve/reject handlers
  const handlePrincipleApprove = useCallback((nodeId: string) => {
    bridge.sendPrincipleApproved(nodeId)
    setNodes(nds => nds.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, status: 'approved' } } : n
    ))
  }, [setNodes])

  const handlePrincipleReject = useCallback((nodeId: string) => {
    bridge.sendPrincipleRejected(nodeId)
    setNodes(nds => nds.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, status: 'rejected' } } : n
    ))
  }, [setNodes])

  // Annotation text change handler
  const handleAnnotationTextChange = useCallback((nodeId: string, text: string) => {
    bridge.sendAnnotationUpdated(nodeId, text)
    setNodes(nds => nds.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, text } } : n
    ))
  }, [setNodes])

  // Annotation delete handler
  const handleAnnotationDelete = useCallback((nodeId: string) => {
    bridge.sendAnnotationDeleted(nodeId)
    setNodes(nds => nds.filter(n => n.id !== nodeId))
  }, [setNodes])

  // Group label change handler
  const handleGroupLabelChange = useCallback((nodeId: string, label: string) => {
    bridge.sendGroupUpdated(nodeId, label)
    setNodes(nds => nds.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, label } } : n
    ))
  }, [setNodes])

  // Inject callbacks into node data so nodes can call bridge actions
  const enrichedNodes = useMemo(() => nodes.map(n => {
    if (n.type === 'principle') {
      return { ...n, data: { ...n.data, nodeId: n.id, onApprove: handlePrincipleApprove, onReject: handlePrincipleReject } }
    }
    if (n.type === 'annotation') {
      return { ...n, data: { ...n.data, nodeId: n.id, onTextChange: handleAnnotationTextChange, onDelete: handleAnnotationDelete } }
    }
    if (n.type === 'group') {
      return { ...n, data: { ...n.data, nodeId: n.id, onLabelChange: handleGroupLabelChange } }
    }
    return n
  }), [nodes, handlePrincipleApprove, handlePrincipleReject, handleAnnotationTextChange, handleAnnotationDelete, handleGroupLabelChange])

  // Register bridge handlers and signal ready
  useEffect(() => {
    bridge.onLoadWorkflow((data) => {
      setNodes(data.nodes.map(n => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data as NodeData,
        ...(n.data.parentId ? { parentId: n.data.parentId as string, extent: 'parent' as const } : {}),
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
      setNodes(nds => nds.map(n =>
        n.id === nodeId ? { ...n, data: { ...n.data, status } } : n
      ))
    })

    // Swift → React global handlers
    // @ts-expect-error — global window extensions for Swift bridge
    window.loadBoard = (json: string) => {
      try {
        const data = JSON.parse(json)
        // loadBoard reuses the loadWorkflow handler
        bridge._handleLoadWorkflow(data)
      } catch (e) {
        console.error('[research-bridge] Failed to parse board data:', e)
      }
    }

    // @ts-expect-error — global window extensions for Swift bridge
    window.updatePrincipleStatus = (nodeId: string, status: string) => {
      setNodes(nds => nds.map(n =>
        n.id === nodeId ? { ...n, data: { ...n.data, status } } : n
      ))
    }

    // @ts-expect-error — global window extensions for Swift bridge
    window.highlightEntity = (entityId: string) => {
      setNodes(nds => nds.map(n => ({
        ...n,
        selected: n.id === entityId,
      })))
    }

    // @ts-expect-error — global window extensions for Swift bridge
    window.addNodeToCanvas = (json: string) => {
      try {
        const nodeData = JSON.parse(json)
        const newNode: CanvasNode = {
          id: nodeData.id ?? `node-${Date.now()}`,
          type: nodeData.type ?? 'entity',
          position: nodeData.position ?? { x: 100, y: 100 },
          data: nodeData.data ?? {},
        }
        setNodes(nds => [...nds, newNode])
      } catch (e) {
        console.error('[research-bridge] Failed to parse node data:', e)
      }
    }

    bridge.signalReady()
  }, [setNodes, setEdges])

  // Forward position changes to Swift
  const handleNodesChange = useCallback(
    (changes: NodeChange<CanvasNode>[]) => {
      onNodesChange(changes)
      const moved = changes.filter(
        (c): c is NodeChange & { type: 'position'; position: { x: number; y: number } } =>
          c.type === 'position' && 'position' in c && c.position != null
      )
      if (moved.length > 0) {
        bridge.sendNodesMoved(
          moved.map(c => ({ id: c.id, x: c.position.x, y: c.position.y }))
        )
      }
    },
    [onNodesChange]
  )

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<CanvasEdge>[]) => {
      onEdgesChange(changes)
      const removed = changes.filter(c => c.type === 'remove')
      removed.forEach(c => bridge.sendEdgeDeleted(c.id))
    },
    [onEdgesChange]
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge(connection, eds))
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
    deleted.forEach(n => bridge.sendNodeDeleted(n.id))
  }, [])

  // Track multi-selection for FloatingActionBar
  const onSelectionChange = useCallback(({ nodes: selectedNodes }: OnSelectionChangeParams) => {
    const ids = selectedNodes.map(n => n.id)
    setSelectedNodeIds(ids)

    if (ids.length >= 2) {
      bridge.sendNodesSelected(ids)

      // Compute average position for action bar placement
      const avgX = selectedNodes.reduce((sum, n) => sum + (n.position?.x ?? 0), 0) / selectedNodes.length
      const avgY = selectedNodes.reduce((sum, n) => sum + (n.position?.y ?? 0), 0) / selectedNodes.length

      // Convert flow coordinates to screen coordinates for positioning
      try {
        const screenPos = screenToFlowPosition({ x: avgX, y: avgY })
        // Use the avg position directly since the bar is inside the ReactFlow panel
        setSelectionCenter({ x: avgX, y: screenPos.y })
      } catch {
        setSelectionCenter({ x: avgX, y: avgY })
      }
    }
  }, [screenToFlowPosition])

  // FloatingActionBar actions
  const handleDistill = useCallback(() => {
    bridge.sendDistillRequested(selectedNodeIds)
  }, [selectedNodeIds])

  const handleGroup = useCallback(() => {
    const groupId = `group-${Date.now()}`
    const selectedNodes = nodes.filter(n => selectedNodeIds.includes(n.id))

    // Calculate bounding box
    const minX = Math.min(...selectedNodes.map(n => n.position.x)) - 20
    const minY = Math.min(...selectedNodes.map(n => n.position.y)) - 40
    const maxX = Math.max(...selectedNodes.map(n => n.position.x)) + 280
    const maxY = Math.max(...selectedNodes.map(n => n.position.y)) + 120

    const groupNode: CanvasNode = {
      id: groupId,
      type: 'group',
      position: { x: minX, y: minY },
      data: { label: 'New Group' },
      style: { width: maxX - minX, height: maxY - minY },
    }

    // Move selected nodes inside group (adjust positions relative to group)
    setNodes(nds => {
      const updated = nds.map(n => {
        if (selectedNodeIds.includes(n.id)) {
          return {
            ...n,
            parentId: groupId,
            extent: 'parent' as const,
            position: {
              x: n.position.x - minX,
              y: n.position.y - minY,
            },
          }
        }
        return n
      })
      return [groupNode, ...updated]
    })

    bridge.sendGroupCreated(groupId, selectedNodeIds, 'New Group')
    setSelectedNodeIds([])
  }, [nodes, selectedNodeIds, setNodes])

  const handleRemove = useCallback(() => {
    setNodes(nds => nds.filter(n => !selectedNodeIds.includes(n.id)))
    setEdges(eds => eds.filter(e =>
      !selectedNodeIds.includes(e.source) && !selectedNodeIds.includes(e.target)
    ))
    selectedNodeIds.forEach(id => bridge.sendNodeDeleted(id))
    setSelectedNodeIds([])
  }, [selectedNodeIds, setNodes, setEdges])

  // MiniMap node color by type
  const minimapNodeColor = useCallback((node: Node) => {
    const colors: Record<string, string> = {
      entity: nodeColors.entity.dot,
      fact: nodeColors.fact.dot,
      principle: nodeColors.principle.dot,
      memory: nodeColors.memory.dot,
      annotation: nodeColors.annotation.dot,
      group: 'rgba(224,160,80,0.2)',
    }
    return colors[node.type ?? ''] ?? nodeColors.entity.dot
  }, [])

  return (
    <div style={{ width: '100vw', height: '100vh', ...darkTheme.container }}>
      <ReactFlow
        nodes={enrichedNodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodesDelete={onNodesDelete}
        onSelectionChange={onSelectionChange}
        nodeTypes={researchNodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        selectionOnDrag
        panOnDrag={[1, 2]}
        proOptions={{ hideAttribution: true }}
        deleteKeyCode={['Backspace', 'Delete']}
        multiSelectionKeyCode="Meta"
      >
        <Controls showInteractive={false} />
        <MiniMap
          style={darkTheme.minimap}
          nodeColor={minimapNodeColor}
          maskColor={darkTheme.minimap.maskColor}
        />
        <Background variant={BackgroundVariant.Dots} color="rgba(228,223,215,0.04)" gap={20} />
      </ReactFlow>
      {selectedNodeIds.length >= 2 && (
        <FloatingActionBar
          selectedCount={selectedNodeIds.length}
          position={selectionCenter}
          onDistill={handleDistill}
          onGroup={handleGroup}
          onRemove={handleRemove}
        />
      )}
    </div>
  )
}

export default function ResearchApp() {
  return (
    <ReactFlowProvider>
      <ResearchCanvas />
    </ReactFlowProvider>
  )
}
