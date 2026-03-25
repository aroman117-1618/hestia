/** Canvas context — which canvas is sending the message */
export type CanvasContext = 'workflow' | 'research';

/** Messages from React → Swift */
export type BridgeAction =
  | { type: 'ready'; canvas: CanvasContext }
  | { type: 'nodesMoved'; canvas: CanvasContext; payload: { moves: Array<{ id: string; x: number; y: number }> } }
  | { type: 'nodeSelected'; canvas: CanvasContext; payload: { nodeId: string } }
  | { type: 'nodeDeleted'; canvas: CanvasContext; payload: { nodeId: string } }
  | { type: 'edgeCreated'; canvas: CanvasContext; payload: { source: string; target: string; sourceHandle?: string } }
  | { type: 'edgeDeleted'; canvas: CanvasContext; payload: { edgeId: string } }
  // Workflow-specific
  | { type: 'addStep'; canvas: 'workflow'; payload: { stepType: string; title: string; positionX: number; positionY: number; afterNodeId?: string } }
  // Research-specific
  | { type: 'nodesSelected'; canvas: 'research'; payload: { nodeIds: string[] } }
  | { type: 'annotationCreated'; canvas: 'research'; payload: { id: string; text: string; x: number; y: number } }
  | { type: 'annotationUpdated'; canvas: 'research'; payload: { id: string; text: string } }
  | { type: 'annotationDeleted'; canvas: 'research'; payload: { id: string } }
  | { type: 'groupCreated'; canvas: 'research'; payload: { id: string; nodeIds: string[]; label: string } }
  | { type: 'groupUpdated'; canvas: 'research'; payload: { id: string; label: string } }
  | { type: 'distillRequested'; canvas: 'research'; payload: { nodeIds: string[] } }
  | { type: 'principleApproved'; canvas: 'research'; payload: { nodeId: string } }
  | { type: 'principleRejected'; canvas: 'research'; payload: { nodeId: string } }
  | { type: 'layoutSaved'; canvas: 'research'; payload: { boardId: string; positions: Array<{ id: string; x: number; y: number }> } }
  | { type: 'crossLinkRequested'; canvas: 'research'; payload: { entityId: string; targetModule: string } };
