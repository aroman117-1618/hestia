// Swift-JS bidirectional bridge for WKWebView communication

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

interface WorkflowData {
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

interface Position {
  id: string
  x: number
  y: number
}

type LoadWorkflowHandler = (data: WorkflowData) => void
type UpdateStatusHandler = (nodeId: string, status: string) => void

let loadWorkflowHandler: LoadWorkflowHandler | null = null
let updateStatusHandler: UpdateStatusHandler | null = null
let debounceTimer: ReturnType<typeof setTimeout> | null = null

export const bridge = {
  signalReady() {
    window.webkit?.messageHandlers?.canvasReady?.postMessage('ready')
  },

  onLoadWorkflow(fn: LoadWorkflowHandler) {
    loadWorkflowHandler = fn
  },

  onUpdateNodeStatus(fn: UpdateStatusHandler) {
    updateStatusHandler = fn
  },

  sendNodesMoved(positions: Position[]) {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      window.webkit?.messageHandlers?.canvasAction?.postMessage(
        JSON.stringify({ type: 'nodesMoved', payload: positions })
      )
    }, 300)
  },

  sendEdgeCreated(connection: { source: string; target: string; sourceHandle?: string | null }) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'edgeCreated', payload: connection })
    )
  },

  sendNodeSelected(nodeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'nodeSelected', payload: { nodeId } })
    )
  },

  sendNodeDeleted(nodeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'nodeDeleted', payload: { nodeId } })
    )
  },

  sendEdgeDeleted(edgeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'edgeDeleted', payload: { edgeId } })
    )
  },

  sendAddStep(payload: {
    title: string
    stepType: string
    positionX: number
    positionY: number
    afterNodeId?: string
  }) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'addStep', payload })
    )
  },
}

// Global functions called from Swift via evaluateJavaScript
window.loadWorkflow = (json: string) => {
  try {
    const data: WorkflowData = JSON.parse(json)
    loadWorkflowHandler?.(data)
  } catch (e) {
    console.error('[bridge] Failed to parse workflow data:', e)
  }
}

window.updateNodeStatus = (nodeId: string, status: string) => {
  updateStatusHandler?.(nodeId, status)
}
