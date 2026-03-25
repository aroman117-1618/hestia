import { useCallback, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap,
  type Node, type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

function generateNodes(count: number): Node[] {
  const nodes: Node[] = [];
  const cols = Math.ceil(Math.sqrt(count));
  for (let i = 0; i < count; i++) {
    nodes.push({
      id: `node-${i}`,
      position: { x: (i % cols) * 220, y: Math.floor(i / cols) * 120 },
      data: {
        label: `Entity ${i}`,
        type: ['entity', 'fact', 'principle', 'memory'][i % 4],
        connections: Math.floor(Math.random() * 12),
      },
      type: 'default',
    });
  }
  return nodes;
}

function generateEdges(nodes: Node[]): Edge[] {
  const edges: Edge[] = [];
  for (let i = 1; i < nodes.length; i++) {
    if (Math.random() > 0.6) {
      edges.push({
        id: `edge-${i}`,
        source: nodes[Math.floor(Math.random() * i)].id,
        target: nodes[i].id,
      });
    }
  }
  return edges;
}

export default function PerformancePrototype() {
  const nodes = useMemo(() => generateNodes(300), []);
  const edges = useMemo(() => generateEdges(nodes), [nodes]);
  const onNodeDrag = useCallback(() => {}, []);

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#110B03' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeDrag={onNodeDrag}
        fitView
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color="rgba(224,160,80,0.06)" gap={24} size={1} />
        <Controls />
        <MiniMap style={{ background: '#0D0802' }} />
      </ReactFlow>
      <div style={{
        position: 'fixed', top: 8, right: 8, background: 'rgba(0,0,0,0.8)',
        color: '#E0A050', padding: '8px 12px', borderRadius: 8, fontSize: 12,
      }}>
        PERF TEST: {nodes.length} nodes, {edges.length} edges
      </div>
    </div>
  );
}
