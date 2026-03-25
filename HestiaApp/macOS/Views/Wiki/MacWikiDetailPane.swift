import SwiftUI
import HestiaShared

struct MacWikiDetailPane: View {
    @ObservedObject var viewModel: WikiViewModel
    @State private var showingGenerateAllAlert = false

    var body: some View {
        VStack(spacing: 0) {
            toolbar
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            if let error = viewModel.errorMessage, !viewModel.articles.isEmpty {
                errorBanner(error)
            }

            if viewModel.isLoading && viewModel.articles.isEmpty {
                loadingState
            } else if let error = viewModel.errorMessage, viewModel.articles.isEmpty {
                errorState(error)
            } else if viewModel.showingRoadmap {
                WikiRoadmapView(viewModel: viewModel)
            } else if let article = viewModel.selectedArticle {
                articleContent(article)
            } else {
                tabLanding
            }
        }
    }

    // MARK: - Toolbar

    private var toolbar: some View {
        HStack(spacing: MacSpacing.md) {
            if viewModel.selectedArticle != nil && !viewModel.showingRoadmap {
                Button {
                    viewModel.selectedArticleId = nil
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                            .font(MacTypography.sectionLabel)
                        Text(viewModel.selectedTab.rawValue)
                            .font(MacTypography.labelMedium)
                    }
                    .foregroundStyle(MacColors.amberAccent)
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Back")
                .hoverCursor(.pointingHand)
            }

            Text(toolbarTitle)
                .font(MacTypography.sectionTitle)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            if viewModel.isGenerating {
                ProgressView()
                    .controlSize(.small)
                    .tint(MacColors.amberAccent)
                Text("Generating...")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textSecondary)
            }

            Button {
                Task { await viewModel.refreshStaticContent() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Refresh articles")
            .hoverCursor(.pointingHand)
            .disabled(viewModel.isLoading)

            Button {
                showingGenerateAllAlert = true
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                    Text("Generate All")
                }
                .font(MacTypography.smallMedium)
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 4)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Generate all articles")
            .hoverCursor(.pointingHand)
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

    private var toolbarTitle: String {
        if viewModel.showingRoadmap {
            return "Roadmap"
        }
        if let article = viewModel.selectedArticle {
            return article.title
        }
        return viewModel.selectedTab.rawValue
    }

    // MARK: - Tab Landing

    private var tabLanding: some View {
        ScrollView {
            VStack(spacing: MacSpacing.xl) {
                // Diagram hero
                diagramForCurrentTab
                    .padding(.horizontal, MacSpacing.xl)
                    .padding(.top, MacSpacing.lg)

                // Article card grid
                if !viewModel.currentTabArticles.isEmpty {
                    articleCardGrid
                        .padding(.horizontal, MacSpacing.xl)
                        .padding(.bottom, MacSpacing.xl)
                } else {
                    emptyTabState
                        .padding(.top, MacSpacing.xl)
                }
            }
        }
    }

    @ViewBuilder
    private var diagramForCurrentTab: some View {
        switch viewModel.selectedTab {
        case .overview:
            ArchitectureDiagramView()
        case .core:
            RequestLifecycleDiagramView()
        case .skills:
            CouncilFlowDiagramView()
        case .memory:
            DataFlowDiagramView()
        case .resources:
            IntegrationMapDiagramView()
        }
    }

    private var articleCardGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: MacSpacing.md),
            GridItem(.flexible(), spacing: MacSpacing.md)
        ], spacing: MacSpacing.md) {
            ForEach(viewModel.currentTabArticles) { article in
                ArticleCardView(article: article, viewModel: viewModel)
            }
        }
    }

    private var emptyTabState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "sparkles")
                .font(MacTypography.largeValue)
                .foregroundStyle(MacColors.amberAccent.opacity(0.4))
            Text("No articles generated yet")
                .font(MacTypography.bodyMedium)
                .foregroundStyle(MacColors.textSecondary)
            Text("Use \"Generate All\" to create AI-written narratives for each module")
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 280)
        }
        .padding(.bottom, MacSpacing.xxxl)
    }

    // MARK: - Article Content

    private func articleContent(_ article: WikiArticle) -> some View {
        VStack(spacing: 0) {
            articleHeader(article)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.lg)

            if article.content.isEmpty {
                notGeneratedState(article)
            } else {
                MarkdownWebView(
                    content: article.content,
                    articleId: article.id,
                    isDiagram: article.type == .diagram
                )
            }
        }
    }

    private func articleHeader(_ article: WikiArticle) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: article.type == .module ? article.moduleIcon : article.type.iconName)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.amberAccent)
                Text(article.title)
                    .font(MacTypography.pageTitle)
                    .foregroundStyle(MacColors.textPrimary)
            }

            HStack(spacing: MacSpacing.md) {
                Text(article.subtitle)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)

                Spacer()

                if article.wordCount > 0 {
                    Text(article.readTimeBadge)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(MacColors.innerPillBackground)
                        .cornerRadius(4)
                }

                statusBadge(for: article)
            }
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.top, MacSpacing.lg)
        .padding(.bottom, MacSpacing.sm)
    }

    private func notGeneratedState(_ article: WikiArticle) -> some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "sparkles")
                .font(MacTypography.largeValue)
                .foregroundStyle(MacColors.amberAccent.opacity(0.4))
            Text("This article hasn't been generated yet")
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textSecondary)
            Text("Generate it using the cloud LLM to create an AI-written narrative")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 300)
            generateButton(for: article)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
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
                .font(MacTypography.caption)
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
            .font(MacTypography.labelMedium)
            .foregroundStyle(MacColors.amberAccent)
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.activeTabBackground)
            .cornerRadius(MacCornerRadius.treeItem)
        }
        .buttonStyle(.hestia)
        .disabled(viewModel.isGenerating)
    }

    // MARK: - Error Banner

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.healthRed)
            Text(message)
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.textSecondary)
                .lineLimit(2)
            Spacer()
            Button {
                viewModel.errorMessage = nil
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(MacColors.textFaint)
            }
            .buttonStyle(.hestia)
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.healthRed.opacity(0.08))
    }

    // MARK: - States

    private var loadingState: some View {
        VStack {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Text("Loading articles...")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
                .padding(.top, MacSpacing.sm)
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
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textSecondary)
            Text("Make sure the Hestia server is running")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textFaint)
            Button {
                Task { await viewModel.loadArticles() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.clockwise")
                    Text("Retry")
                }
                .font(MacTypography.labelMedium)
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.sm)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.hestia)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Article Card View (for Tab Landing Grid)

private struct ArticleCardView: View {
    let article: WikiArticle
    let viewModel: WikiViewModel
    @State private var isHovered = false

    var body: some View {
        Button {
            viewModel.selectArticle(article)
        } label: {
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: article.moduleIcon)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.amberAccent)
                        .frame(width: 20)
                    Text(article.title)
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)
                    Spacer()
                }

                if !article.subtitle.isEmpty {
                    Text(article.subtitle)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(2)
                }

                HStack(spacing: MacSpacing.sm) {
                    if article.wordCount > 0 {
                        Text(article.readTimeBadge)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textFaint)
                    }

                    Spacer()

                    Circle()
                        .fill(article.isGenerated ? MacColors.healthGreen :
                              article.isStatic ? MacColors.amberAccent :
                              MacColors.healthRed.opacity(0.6))
                        .frame(width: 5, height: 5)
                    Text(article.isGenerated ? "Generated" :
                         article.isStatic ? "Static" : "Pending")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)

                    if article.content.isEmpty {
                        Button {
                            Task {
                                await viewModel.generateArticle(
                                    type: article.articleType,
                                    moduleName: article.moduleName
                                )
                            }
                        } label: {
                            Image(systemName: "sparkles")
                                .font(MacTypography.metadata)
                                .foregroundStyle(MacColors.amberAccent)
                        }
                        .buttonStyle(.hestia)
                    }
                }
            }
            .padding(MacSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .fill(isHovered ? MacColors.activeNavBackground.opacity(0.5) : MacColors.panelBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.hestia)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
    }
}
