import SwiftUI
@preconcurrency import WebKit

/// WKWebView wrapper that renders the React Flow workflow canvas.
///
/// Loads `WorkflowCanvas/index.html` once via `loadFileURL()` (gives sibling JS/CSS access),
/// then injects workflow data via `loadWorkflow(...)` and receives canvas actions back
/// through `canvasAction` message handler.
struct WorkflowCanvasWebView: NSViewRepresentable {
    let workflowDetail: WorkflowDetail?
    var nodeStatuses: [String: String]  // nodeId → "running" | "success" | "failed"
    let onNodeSelected: (String) -> Void
    let onNodesMoved: ([(id: String, x: Double, y: Double)]) -> Void
    let onEdgeCreated: (String, String, String?) -> Void  // source, target, sourceHandle
    let onNodeDeleted: (String) -> Void
    let onEdgeDeleted: (String) -> Void
    var onAddStep: ((String, String, Double, Double, String?) -> Void)?

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onNodeSelected: onNodeSelected,
            onNodesMoved: onNodesMoved,
            onEdgeCreated: onEdgeCreated,
            onNodeDeleted: onNodeDeleted,
            onEdgeDeleted: onEdgeDeleted,
            onAddStep: onAddStep
        )
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let coordinator = context.coordinator

        // Harden WebView: disable developer extras in release
        #if !DEBUG
        config.preferences.setValue(false, forKey: "developerExtrasEnabled")
        #endif

        config.userContentController.add(coordinator, name: "canvasReady")
        config.userContentController.add(coordinator, name: "canvasAction")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = coordinator

        // Transparent background — prevents white flash on dark UI
        webView.setValue(false, forKey: "drawsBackground")

        coordinator.webView = webView

        // Load bundled canvas HTML — loadFileURL grants access to sibling JS/CSS files
        if let url = Bundle.main.url(
            forResource: "index",
            withExtension: "html",
            subdirectory: "WorkflowCanvas"
        ) {
            let resourceDir = url.deletingLastPathComponent()
            webView.loadFileURL(url, allowingReadAccessTo: resourceDir)
        }

        // Queue initial workflow if already available
        if let detail = workflowDetail {
            coordinator.pendingDetail = detail
        }

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let coordinator = context.coordinator

        // Inject workflow if the selected workflow changed
        if let detail = workflowDetail,
           coordinator.currentWorkflowId != detail.id {
            if coordinator.canvasReady {
                coordinator.injectWorkflow(detail)
            } else {
                coordinator.pendingDetail = detail
            }
        }

        // Forward execution status updates to canvas node coloring
        if coordinator.canvasReady {
            for (nodeId, status) in nodeStatuses {
                coordinator.updateNodeStatus(nodeId, status)
            }
        }
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var webView: WKWebView?
        var canvasReady = false
        var currentWorkflowId: String?
        var pendingDetail: WorkflowDetail?

        let onNodeSelected: (String) -> Void
        let onNodesMoved: ([(id: String, x: Double, y: Double)]) -> Void
        let onEdgeCreated: (String, String, String?) -> Void
        let onNodeDeleted: (String) -> Void
        let onEdgeDeleted: (String) -> Void
        var onAddStep: ((String, String, Double, Double, String?) -> Void)?

        init(
            onNodeSelected: @escaping (String) -> Void,
            onNodesMoved: @escaping ([(id: String, x: Double, y: Double)]) -> Void,
            onEdgeCreated: @escaping (String, String, String?) -> Void,
            onNodeDeleted: @escaping (String) -> Void,
            onEdgeDeleted: @escaping (String) -> Void,
            onAddStep: ((String, String, Double, Double, String?) -> Void)? = nil
        ) {
            self.onNodeSelected = onNodeSelected
            self.onNodesMoved = onNodesMoved
            self.onEdgeCreated = onEdgeCreated
            self.onNodeDeleted = onNodeDeleted
            self.onEdgeDeleted = onEdgeDeleted
            self.onAddStep = onAddStep
        }

        // MARK: - WKScriptMessageHandler

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            switch message.name {
            case "canvasReady":
                canvasReady = true
                if let pending = pendingDetail {
                    injectWorkflow(pending)
                    pendingDetail = nil
                }
            case "canvasAction":
                guard let body = message.body as? String,
                      let data = body.data(using: .utf8),
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let type = json["type"] as? String,
                      let payload = json["payload"]
                else { return }
                handleCanvasAction(type: type, payload: payload)
            default:
                break
            }
        }

        private func handleCanvasAction(type: String, payload: Any) {
            switch type {
            case "nodeSelected":
                if let dict = payload as? [String: Any],
                   let nodeId = dict["nodeId"] as? String {
                    onNodeSelected(nodeId)
                }
            case "nodesMoved":
                if let positions = payload as? [[String: Any]] {
                    let mapped: [(id: String, x: Double, y: Double)] = positions.compactMap { p in
                        guard let id = p["id"] as? String,
                              let x = p["x"] as? Double,
                              let y = p["y"] as? Double
                        else { return nil }
                        return (id: id, x: x, y: y)
                    }
                    onNodesMoved(mapped)
                }
            case "edgeCreated":
                if let dict = payload as? [String: Any],
                   let source = dict["source"] as? String,
                   let target = dict["target"] as? String {
                    onEdgeCreated(source, target, dict["sourceHandle"] as? String)
                }
            case "nodeDeleted":
                if let dict = payload as? [String: Any],
                   let nodeId = dict["nodeId"] as? String {
                    onNodeDeleted(nodeId)
                }
            case "edgeDeleted":
                if let dict = payload as? [String: Any],
                   let edgeId = dict["edgeId"] as? String {
                    onEdgeDeleted(edgeId)
                }
            case "addStep":
                guard let dict = payload as? [String: Any],
                      let stepType = dict["stepType"] as? String,
                      let title = dict["title"] as? String,
                      let posX = dict["positionX"] as? Double,
                      let posY = dict["positionY"] as? Double else { return }
                let afterNodeId = dict["afterNodeId"] as? String
                onAddStep?(stepType, title, posX, posY, afterNodeId)
            default:
                #if DEBUG
                print("[CanvasWebView] Unknown action: \(type)")
                #endif
            }
        }

        // MARK: - Workflow Injection

        func injectWorkflow(_ detail: WorkflowDetail) {
            guard let webView else { return }
            currentWorkflowId = detail.id

            // Convert WorkflowDetail to React Flow format
            var rfNodes: [[String: Any]] = []
            for node in detail.nodes {
                // Build config as plain [String: Any] for JSON serialization
                var configDict: [String: Any] = [:]
                for (key, val) in node.config {
                    if let encoded = try? JSONEncoder().encode(val),
                       let obj = try? JSONSerialization.jsonObject(with: encoded) {
                        configDict[key] = obj
                    }
                }
                rfNodes.append([
                    "id": node.id,
                    "type": node.nodeType,  // Maps to custom node components
                    "position": ["x": node.positionX, "y": node.positionY],
                    "data": [
                        "label": node.label,
                        "nodeType": node.nodeType,
                        "config": configDict,
                    ] as [String: Any],
                ])
            }

            var rfEdges: [[String: Any]] = []
            for edge in detail.edges {
                var e: [String: Any] = [
                    "id": edge.id,
                    "source": edge.sourceNodeId,
                    "target": edge.targetNodeId,
                ]
                if !edge.edgeLabel.isEmpty {
                    e["label"] = edge.edgeLabel
                    e["sourceHandle"] = edge.edgeLabel
                }
                rfEdges.append(e)
            }

            let payload: [String: Any] = ["nodes": rfNodes, "edges": rfEdges]
            guard let jsonData = try? JSONSerialization.data(withJSONObject: payload),
                  let jsonString = String(data: jsonData, encoding: .utf8)
            else { return }

            let escaped = jsonString
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "'", with: "\\'")
                .replacingOccurrences(of: "\n", with: "\\n")

            webView.evaluateJavaScript("loadWorkflow('\(escaped)')") { _, error in
                #if DEBUG
                if let error { print("[CanvasWebView] loadWorkflow error: \(error)") }
                #endif
            }
        }

        /// Forward execution status to canvas for node coloring
        func updateNodeStatus(_ nodeId: String, _ status: String) {
            webView?.evaluateJavaScript("updateNodeStatus('\(nodeId)', '\(status)')") { _, _ in }
        }

        // MARK: - Navigation Policy (block all external navigation)

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void
        ) {
            if navigationAction.navigationType == .other {
                decisionHandler(.allow)
                return
            }
            decisionHandler(.cancel)
        }
    }
}
