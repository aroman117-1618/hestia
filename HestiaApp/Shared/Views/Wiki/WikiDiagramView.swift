import SwiftUI
import WebKit
import HestiaShared

/// Diagram list tab — shows generated Mermaid diagrams
struct WikiDiagramListView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.md) {
                if viewModel.diagramArticles.isEmpty {
                    emptyState
                } else {
                    ForEach(viewModel.diagramArticles) { article in
                        NavigationLink(destination: WikiDiagramDetailView(article: article)) {
                            diagramCard(article)
                        }
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.bottom, Spacing.xxl)
        }
    }

    // MARK: - Diagram Card

    private func diagramCard(_ article: WikiArticle) -> some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: article.moduleIcon)
                .font(.system(size: 20))
                .foregroundColor(.textPrimary)
                .frame(width: 40, height: 40)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.small)

            VStack(alignment: .leading, spacing: 2) {
                Text(article.title)
                    .font(.cardTitle)
                    .foregroundColor(.textPrimary)

                Text(article.subtitle)
                    .font(.caption)
                    .foregroundColor(.textSecondary)
            }

            Spacer()

            if article.isGenerated {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.healthyGreen)
                    .font(.caption)
            }

            Image(systemName: "chevron.right")
                .foregroundColor(.textTertiary)
                .font(.caption)
        }
        .settingsRow()
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
                .frame(height: Spacing.xxl)

            Image(systemName: "diagram.flow")
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            VStack(spacing: Spacing.sm) {
                Text("Architecture Diagrams")
                    .font(.headline)
                    .foregroundColor(.textSecondary)

                Text("Generate Mermaid diagrams showing system architecture, request lifecycle, and data flow.")
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }

            Button {
                Task {
                    await viewModel.generateAll()
                }
            } label: {
                HStack(spacing: Spacing.sm) {
                    if viewModel.isGenerating {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "sparkles")
                    }
                    Text("Generate All (~$0.80)")
                }
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.textPrimary)
                .padding(.horizontal, Spacing.lg)
                .padding(.vertical, Spacing.sm)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.small)
            }
            .disabled(viewModel.isGenerating)
        }
    }
}

// MARK: - Diagram Detail View (Mermaid rendering)

struct WikiDiagramDetailView: View {
    let article: WikiArticle

    var body: some View {
        ZStack {
            Color.bgBase.ignoresSafeArea()

            if article.isGenerated {
                MermaidWebView(mermaidSource: article.content)
                    .ignoresSafeArea(edges: .bottom)
            } else {
                VStack(spacing: Spacing.lg) {
                    Spacer()
                    Image(systemName: "diagram.flow")
                        .font(.system(size: 48))
                        .foregroundColor(.textTertiary)
                    Text("Diagram not generated yet")
                        .foregroundColor(.textTertiary)
                    Spacer()
                }
            }
        }
        .navigationTitle(article.title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Mermaid Web View

struct MermaidWebView: UIViewRepresentable {
    let mermaidSource: String

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let html = mermaidHTML(source: mermaidSource)
        webView.loadHTMLString(html, baseURL: nil)
    }

    private func mermaidHTML(source: String) -> String {
        // Escape content for embedding in HTML
        let escaped = source
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "`", with: "\\`")
            .replacingOccurrences(of: "$", with: "\\$")

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0">
            <style>
                body {
                    background-color: #000000;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    padding: 20px;
                    margin: 0;
                    min-height: 100vh;
                }
                .mermaid {
                    max-width: 100%;
                }
                .mermaid svg {
                    max-width: 100%;
                    height: auto;
                }
            </style>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({
                    startOnLoad: true,
                    theme: 'dark',
                    themeVariables: {
                        primaryColor: '#1a1a2e',
                        primaryTextColor: '#ffffff',
                        primaryBorderColor: '#4a4a6a',
                        lineColor: '#6a6a8a',
                        secondaryColor: '#16213e',
                        tertiaryColor: '#0f3460',
                        fontSize: '14px'
                    }
                });
            </script>
        </head>
        <body>
            <div class="mermaid">
        \(escaped)
            </div>
        </body>
        </html>
        """
    }
}

// MARK: - Preview

struct WikiDiagramView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiDiagramListView(viewModel: WikiViewModel())
        }
        .preferredColorScheme(.dark)
    }
}
