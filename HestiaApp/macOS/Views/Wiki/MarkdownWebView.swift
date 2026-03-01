import SwiftUI
@preconcurrency import WebKit

/// WKWebView wrapper that renders markdown content using bundled JS libraries.
///
/// Loads `wiki-template.html` once via `loadFileURL()` (gives sibling JS file access),
/// then injects content per article via `evaluateJavaScript("renderMarkdown(...)")`.
/// This avoids full page reloads — article switching is ~5ms JS injection.
struct MarkdownWebView: NSViewRepresentable {
    let content: String
    let articleId: String
    let isDiagram: Bool

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()

        // Register message handler for template-ready signal
        let coordinator = context.coordinator
        config.userContentController.add(coordinator, name: "templateReady")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = coordinator

        // Transparent background — prevents white flash on dark UI
        webView.setValue(false, forKey: "drawsBackground")

        coordinator.webView = webView

        // Load template from bundle — loadFileURL grants access to sibling JS files
        if let templateURL = Bundle.main.url(forResource: "wiki-template", withExtension: "html", subdirectory: "WikiResources") {
            let resourceDir = templateURL.deletingLastPathComponent()
            webView.loadFileURL(templateURL, allowingReadAccessTo: resourceDir)
        }

        // Queue initial content
        coordinator.pendingContent = content
        coordinator.pendingArticleId = articleId
        coordinator.pendingIsDiagram = isDiagram

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let coordinator = context.coordinator

        // Skip if same article
        guard coordinator.currentArticleId != articleId else { return }

        if coordinator.templateLoaded {
            coordinator.injectContent(content, articleId: articleId, isDiagram: isDiagram)
        } else {
            // Template still loading — queue for delivery
            coordinator.pendingContent = content
            coordinator.pendingArticleId = articleId
            coordinator.pendingIsDiagram = isDiagram
        }
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var webView: WKWebView?
        var templateLoaded = false
        var currentArticleId: String?

        // Queued content if it arrives before template is ready
        var pendingContent: String?
        var pendingArticleId: String?
        var pendingIsDiagram: Bool?

        // MARK: - WKScriptMessageHandler

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            onTemplateReady()
        }

        private func onTemplateReady() {
            templateLoaded = true

            // Deliver any queued content
            if let content = pendingContent,
               let articleId = pendingArticleId,
               let isDiagram = pendingIsDiagram {
                injectContent(content, articleId: articleId, isDiagram: isDiagram)
                pendingContent = nil
                pendingArticleId = nil
                pendingIsDiagram = nil
            }
        }

        // MARK: - Content Injection

        func injectContent(_ content: String, articleId: String, isDiagram: Bool) {
            guard let webView else { return }

            currentArticleId = articleId

            // Escape content for JavaScript string literal
            let escaped = content
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "`", with: "\\`")
                .replacingOccurrences(of: "$", with: "\\$")
                .replacingOccurrences(of: "\n", with: "\\n")
                .replacingOccurrences(of: "\r", with: "\\r")

            let js = "renderMarkdown(`\(escaped)`, \(isDiagram))"
            webView.evaluateJavaScript(js) { _, error in
                #if DEBUG
                if let error {
                    print("[MarkdownWebView] JS error: \(error.localizedDescription)")
                }
                #endif
            }
        }

        // MARK: - WKNavigationDelegate

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void
        ) {
            // Allow initial file load and JS-triggered navigations
            if navigationAction.navigationType == .other {
                decisionHandler(.allow)
                return
            }

            // External links open in system browser
            if let url = navigationAction.request.url,
               url.scheme == "https" || url.scheme == "http" {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }

            // Anchor links (scroll within page) — allow
            if navigationAction.request.url?.fragment != nil {
                decisionHandler(.allow)
                return
            }

            decisionHandler(.cancel)
        }
    }
}
