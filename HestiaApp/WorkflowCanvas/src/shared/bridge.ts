// Swift-JS bidirectional bridge for WKWebView communication
import type { CanvasContext, BridgeAction } from './types'

declare global {
  interface Window {
    webkit?: {
      messageHandlers?: {
        canvasReady?: { postMessage: (msg: string) => void }
        canvasAction?: { postMessage: (msg: string) => void }
      }
    }
    loadWorkflow?: (json: string) => void
    updateNodeStatus?: (nodeId: string, status: string) => void
  }
}

export interface WorkflowData {
  nodes: Array<{
    id: string
    type: string
    position: { x: number; y: number }
    data: Record<string, unknown>
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    sourceHandle?: string
    label?: string
  }>
}

type LoadWorkflowHandler = (data: WorkflowData) => void
type UpdateStatusHandler = (nodeId: string, status: string) => void

function postAction(action: BridgeAction): void {
  window.webkit?.messageHandlers?.canvasAction?.postMessage(JSON.stringify(action))
}

/**
 * Factory that returns a typed bridge bound to a specific canvas context.
 * All messages include the canvas discriminator so Swift can route them correctly.
 */
export function createBridge(canvas: CanvasContext) {
  let loadWorkflowHandler: LoadWorkflowHandler | null = null
  let updateStatusHandler: UpdateStatusHandler | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  const bridge = {
    signalReady() {
      // canvasReady is a separate handler (backward compat with workflow canvas)
      window.webkit?.messageHandlers?.canvasReady?.postMessage('ready')
    },

    onLoadWorkflow(fn: LoadWorkflowHandler) {
      loadWorkflowHandler = fn
    },

    onUpdateNodeStatus(fn: UpdateStatusHandler) {
      updateStatusHandler = fn
    },

    sendNodesMoved(positions: Array<{ id: string; x: number; y: number }>) {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        // Swift parses nodesMoved payload as a flat array (not { moves: [...] }).
        // Send the raw array to maintain backward compatibility with WorkflowCanvasWebView.swift.
        window.webkit?.messageHandlers?.canvasAction?.postMessage(
          JSON.stringify({ type: 'nodesMoved', canvas, payload: positions })
        )
      }, 300)
    },

    sendEdgeCreated(connection: { source: string; target: string; sourceHandle?: string | null }) {
      postAction({
        type: 'edgeCreated',
        canvas,
        payload: {
          source: connection.source,
          target: connection.target,
          ...(connection.sourceHandle != null ? { sourceHandle: connection.sourceHandle } : {}),
        },
      })
    },

    sendNodeSelected(nodeId: string) {
      postAction({ type: 'nodeSelected', canvas, payload: { nodeId } })
    },

    sendNodeDeleted(nodeId: string) {
      postAction({ type: 'nodeDeleted', canvas, payload: { nodeId } })
    },

    sendEdgeDeleted(edgeId: string) {
      postAction({ type: 'edgeDeleted', canvas, payload: { edgeId } })
    },

    // Workflow-only
    sendAddStep(payload: {
      title: string
      stepType: string
      positionX: number
      positionY: number
      afterNodeId?: string
    }) {
      postAction({ type: 'addStep', canvas: 'workflow', payload })
    },

    // Research-only helpers
    sendNodesSelected(nodeIds: string[]) {
      postAction({ type: 'nodesSelected', canvas: 'research', payload: { nodeIds } })
    },

    sendAnnotationCreated(id: string, text: string, x: number, y: number) {
      postAction({ type: 'annotationCreated', canvas: 'research', payload: { id, text, x, y } })
    },

    sendAnnotationUpdated(id: string, text: string) {
      postAction({ type: 'annotationUpdated', canvas: 'research', payload: { id, text } })
    },

    sendAnnotationDeleted(id: string) {
      postAction({ type: 'annotationDeleted', canvas: 'research', payload: { id } })
    },

    sendGroupCreated(id: string, nodeIds: string[], label: string) {
      postAction({ type: 'groupCreated', canvas: 'research', payload: { id, nodeIds, label } })
    },

    sendGroupUpdated(id: string, label: string) {
      postAction({ type: 'groupUpdated', canvas: 'research', payload: { id, label } })
    },

    sendDistillRequested(nodeIds: string[]) {
      postAction({ type: 'distillRequested', canvas: 'research', payload: { nodeIds } })
    },

    sendPrincipleApproved(nodeId: string) {
      postAction({ type: 'principleApproved', canvas: 'research', payload: { nodeId } })
    },

    sendPrincipleRejected(nodeId: string) {
      postAction({ type: 'principleRejected', canvas: 'research', payload: { nodeId } })
    },

    sendLayoutSaved(boardId: string, positions: Array<{ id: string; x: number; y: number }>) {
      postAction({ type: 'layoutSaved', canvas: 'research', payload: { boardId, positions } })
    },

    sendCrossLinkRequested(entityId: string, targetModule: string) {
      postAction({ type: 'crossLinkRequested', canvas: 'research', payload: { entityId, targetModule } })
    },

    // Internal — called by global window handlers set up by initBridgeGlobals()
    _handleLoadWorkflow(data: WorkflowData) {
      loadWorkflowHandler?.(data)
    },

    _handleUpdateNodeStatus(nodeId: string, status: string) {
      updateStatusHandler?.(nodeId, status)
    },
  }

  return bridge
}

/**
 * Wire up the global window functions that Swift calls via evaluateJavaScript.
 * Must be called once at app init (before signalReady).
 */
export function initBridgeGlobals(bridge: ReturnType<typeof createBridge>): void {
  window.loadWorkflow = (json: string) => {
    try {
      const data: WorkflowData = JSON.parse(json)
      bridge._handleLoadWorkflow(data)
    } catch (e) {
      console.error('[bridge] Failed to parse workflow data:', e)
    }
  }

  window.updateNodeStatus = (nodeId: string, status: string) => {
    bridge._handleUpdateNodeStatus(nodeId, status)
  }
}
