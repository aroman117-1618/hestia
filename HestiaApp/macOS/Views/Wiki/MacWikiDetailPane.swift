import SwiftUI
import HestiaShared

struct MacWikiDetailPane: View {
    @ObservedObject var viewModel: WikiViewModel
    @State private var selectedArticle: WikiArticle?
    @State private var showingGenerateAllAlert = false

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            toolbar
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            // Content
            if viewModel.isLoading && viewModel.articles.isEmpty {
                loadingState
            } else if let error = viewModel.errorMessage, viewModel.articles.isEmpty {
                errorState(error)
            } else if let article = selectedArticle ?? firstArticle {
                articleContent(article)
            } else {
                emptyState
            }
        }
    }

    // MARK: - Toolbar

    private var toolbar: some View {
        HStack(spacing: MacSpacing.md) {
            Text(viewModel.selectedTab.rawValue)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            if viewModel.isGenerating {
                ProgressView()
                    .controlSize(.small)
                    .tint(MacColors.amberAccent)
                Text("Generating...")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textSecondary)
            }

            Button {
                Task { await viewModel.refreshStaticContent() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 13))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.plain)
            .disabled(viewModel.isLoading)

            Button {
                showingGenerateAllAlert = true
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                    Text("Generate All")
                }
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 4)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.plain)
            .disabled(viewModel.isGenerating)
            .alert("Generate All Articles", isPresented: $showingGenerateAllAlert) {
                Button("Generate") {
                    Task { await viewModel.generateAll() }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will generate all AI-written articles using the cloud LLM. Existing articles will be regenerated.")
            }
        }
    }

    // MARK: - Article Content

    private func articleContent(_ article: WikiArticle) -> some View {
        VStack(spacing: 0) {
            // Native SwiftUI header (stays crisp, matches sidebar)
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: article.type.iconName)
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.amberAccent)
                    Text(article.title)
                        .font(.system(size: 18, weight: .bold))
                        .foregroundStyle(MacColors.textPrimary)
                }

                HStack(spacing: MacSpacing.md) {
                    Text(article.subtitle)
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.textSecondary)

                    Spacer()

                    Text(article.readTimeBadge)
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textFaint)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(MacColors.innerPillBackground)
                        .cornerRadius(4)

                    statusBadge(for: article)
                }
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.top, MacSpacing.lg)
            .padding(.bottom, MacSpacing.sm)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.lg)

            // Rendered markdown content (WKWebView handles its own scrolling)
            MarkdownWebView(
                content: article.content,
                articleId: article.id,
                isDiagram: article.type == .diagram
            )

            // Generate button for pending articles
            if article.isPending {
                generateButton(for: article)
                    .padding(.horizontal, MacSpacing.xl)
                    .padding(.bottom, MacSpacing.lg)
            }
        }
    }

    // MARK: - Status Badge

    private func statusBadge(for article: WikiArticle) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(article.isGenerated ? MacColors.healthGreen :
                      article.isStatic ? MacColors.amberAccent :
                      MacColors.healthRed)
                .frame(width: 6, height: 6)
            Text(article.isGenerated ? "AI Generated" :
                 article.isStatic ? "Static" : "Pending")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
        }
    }

    // MARK: - Generate Button

    private func generateButton(for article: WikiArticle) -> some View {
        Button {
            Task {
                await viewModel.generateArticle(
                    type: article.articleType,
                    moduleName: article.moduleName
                )
            }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "sparkles")
                Text("Generate with AI")
            }
            .font(.system(size: 13, weight: .medium))
            .foregroundStyle(MacColors.amberAccent)
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.activeTabBackground)
            .cornerRadius(MacCornerRadius.treeItem)
        }
        .buttonStyle(.plain)
        .disabled(viewModel.isGenerating)
    }

    // MARK: - States

    private var loadingState: some View {
        VStack {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Text("Loading articles...")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
                .padding(.top, MacSpacing.sm)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "book.closed")
                .font(.system(size: 40))
                .foregroundStyle(MacColors.textFaint)
            Text("No articles in this section")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Refresh static content or generate articles with AI")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 40))
                .foregroundStyle(MacColors.healthRed)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Make sure the Hestia server is running")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
            Button {
                Task { await viewModel.loadArticles() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.clockwise")
                    Text("Retry")
                }
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.sm)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.plain)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Helpers

    private var firstArticle: WikiArticle? {
        switch viewModel.selectedTab {
        case .overview: return viewModel.overviewArticle
        case .modules: return viewModel.moduleArticles.first
        case .decisions: return viewModel.decisionArticles.first
        case .roadmap: return viewModel.roadmapArticle
        case .diagrams: return viewModel.diagramArticles.first
        }
    }
}
