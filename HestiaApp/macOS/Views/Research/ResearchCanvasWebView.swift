import SwiftUI
@preconcurrency import WebKit

/// WKWebView wrapper that renders the React Flow research canvas.
///
/// Loads the bundled `WorkflowCanvas/index.html` with a `#/research` hash route,
/// then communicates with React via a JS bridge (postMessage → WKScriptMessageHandler).
struct ResearchCanvasWebView: NSViewRepresentable {
    /// Shared WKProcessPool for all canvas WebViews (Research + Workflow).
    private static let processPool = WKProcessPool()

    @ObservedObject var viewModel: ResearchCanvasViewModel

    func makeCoordinator() -> Coordinator {
        Coordinator(viewModel: viewModel)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.processPool = Self.processPool
        let coordinator = context.coordinator

        #if !DEBUG
        config.preferences.setValue(false, forKey: "developerExtrasEnabled")
        #endif

        config.userContentController.add(coordinator, name: "canvasReady")
        config.userContentController.add(coordinator, name: "canvasAction")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = coordinator
        webView.setValue(false, forKey: "drawsBackground")
        coordinator.webView = webView

        loadCanvasHTML(into: webView)

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Re-inject board data when currentBoard changes
        if let board = viewModel.currentBoard,
           context.coordinator.canvasReady,
           context.coordinator.currentBoardId != board.id {
            context.coordinator.loadBoard(board.layoutJson)
            context.coordinator.currentBoardId = board.id
        }
    }

    private func loadCanvasHTML(into webView: WKWebView) {
        guard let url = Bundle.main.url(
            forResource: "index",
            withExtension: "html",
            subdirectory: "WorkflowCanvas"
        ) else {
            #if DEBUG
            print("[ResearchCanvasWebView] WorkflowCanvas/index.html not found in bundle")
            #endif
            return
        }

        let resourceDir = url.deletingLastPathComponent()
        // Append #/research hash route so the React app renders the research canvas
        if var components = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            components.fragment = "/research"
            if let hashURL = components.url {
                webView.loadFileURL(hashURL, allowingReadAccessTo: resourceDir)
                return
            }
        }
        // Fallback: load without hash
        webView.loadFileURL(url, allowingReadAccessTo: resourceDir)
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        weak var webView: WKWebView?
        var canvasReady = false
        var currentBoardId: String?
        private weak var viewModel: ResearchCanvasViewModel?

        init(viewModel: ResearchCanvasViewModel) {
            self.viewModel = viewModel
        }

        // MARK: - WKScriptMessageHandler

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            switch message.name {
            case "canvasReady":
                canvasReady = true
                // If a board was queued, inject it now
                if let board = viewModel?.currentBoard {
                    loadBoard(board.layoutJson)
                    currentBoardId = board.id
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
            guard let viewModel else { return }

            switch type {
            case "nodesSelected":
                if let dict = payload as? [String: Any],
                   let ids = dict["nodeIds"] as? [String] {
                    viewModel.selectedNodeIds = ids
                }

            case "distillRequested":
                if let dict = payload as? [String: Any],
                   let ids = dict["nodeIds"] as? [String] {
                    Task { [weak viewModel] in
                        await viewModel?.distillPrinciple(nodeIds: ids)
                    }
                }

            case "principleApproved":
                if let dict = payload as? [String: Any],
                   let id = dict["id"] as? String {
                    Task { [weak viewModel] in
                        await viewModel?.approvePrinciple(id: id)
                    }
                }

            case "principleRejected":
                if let dict = payload as? [String: Any],
                   let id = dict["id"] as? String {
                    Task { [weak viewModel] in
                        await viewModel?.rejectPrinciple(id: id)
                    }
                }

            case "annotationCreated", "annotationUpdated", "annotationDeleted":
                #if DEBUG
                print("[ResearchCanvasWebView] Annotation event: \(type)")
                #endif

            case "groupCreated", "groupUpdated":
                #if DEBUG
                print("[ResearchCanvasWebView] Group event: \(type)")
                #endif

            case "layoutSaved":
                if let dict = payload as? [String: Any],
                   let layoutData = try? JSONSerialization.data(withJSONObject: dict),
                   let layoutString = String(data: layoutData, encoding: .utf8) {
                    viewModel.currentBoard?.layoutJson = layoutString
                    Task { [weak viewModel] in
                        await viewModel?.saveBoard()
                    }
                }

            case "crossLinkRequested":
                #if DEBUG
                if let dict = payload as? [String: Any] {
                    print("[ResearchCanvasWebView] Cross-link requested: \(dict)")
                }
                #endif

            default:
                #if DEBUG
                print("[ResearchCanvasWebView] Unknown action: \(type)")
                #endif
            }
        }

        // MARK: - Swift → React Bridge

        func loadBoard(_ boardJson: String) {
            guard let webView else { return }
            let escaped = boardJson
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "'", with: "\\'")
                .replacingOccurrences(of: "\n", with: "\\n")
            webView.evaluateJavaScript("window.loadBoard && window.loadBoard('\(escaped)')") { _, error in
                #if DEBUG
                if let error { print("[ResearchCanvasWebView] loadBoard error: \(error)") }
                #endif
            }
        }

        func updatePrincipleStatus(_ nodeId: String, status: String) {
            webView?.evaluateJavaScript(
                "window.updatePrincipleStatus && window.updatePrincipleStatus('\(nodeId)', '\(status)')"
            ) { _, _ in }
        }

        func highlightEntity(_ entityId: String) {
            webView?.evaluateJavaScript(
                "window.highlightEntity && window.highlightEntity('\(entityId)')"
            ) { _, _ in }
        }

        func addNodeToCanvas(_ nodeJson: String) {
            guard let webView else { return }
            let escaped = nodeJson
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "'", with: "\\'")
                .replacingOccurrences(of: "\n", with: "\\n")
            webView.evaluateJavaScript("window.addNodeToCanvas && window.addNodeToCanvas('\(escaped)')") { _, error in
                #if DEBUG
                if let error { print("[ResearchCanvasWebView] addNodeToCanvas error: \(error)") }
                #endif
            }
        }

        // MARK: - Navigation Policy

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
