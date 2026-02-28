import SwiftUI
import HestiaShared

/// Main wiki documentation hub — tabbed container for architecture field guide
struct WikiView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = WikiViewModel()
    @State private var showingGenerateConfirmation = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                // Tab selector
                tabSelector

                // Content
                if viewModel.isLoading && viewModel.articles.isEmpty {
                    loadingView
                } else {
                    tabContent
                }
            }
        }
        .navigationTitle("Knowledge")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                // Refresh static content
                Button {
                    Task {
                        await viewModel.refreshStaticContent()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(.white.opacity(0.6))
                }

                // Generate all AI content
                Button {
                    showingGenerateConfirmation = true
                } label: {
                    Image(systemName: "sparkles")
                        .foregroundColor(viewModel.isGenerating ? .white.opacity(0.3) : .white.opacity(0.6))
                }
                .disabled(viewModel.isGenerating)
            }
        }
        .alert("Generate All Content?", isPresented: $showingGenerateConfirmation) {
            Button("Generate (~$0.80)", role: .none) {
                Task {
                    await viewModel.generateAll()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will generate AI narratives for all modules, the overview, and diagrams using your cloud LLM provider.")
        }
        .onAppear {
            Task {
                if viewModel.articles.isEmpty {
                    await viewModel.refreshStaticContent()
                }
            }
        }
    }

    // MARK: - Tab Selector

    private var tabSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 0) {
                ForEach(WikiViewModel.Tab.allCases) { tab in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.selectedTab = tab
                        }
                    } label: {
                        HStack(spacing: Spacing.xs) {
                            Image(systemName: tab.iconName)
                                .font(.caption)

                            Text(tab.rawValue)
                                .font(.subheadline.weight(.semibold))
                        }
                        .foregroundColor(viewModel.selectedTab == tab ? .white : .white.opacity(0.5))
                        .padding(.vertical, Spacing.sm)
                        .padding(.horizontal, Spacing.md)
                        .background(
                            viewModel.selectedTab == tab ?
                            Color.white.opacity(0.2) :
                            Color.clear
                        )
                        .cornerRadius(CornerRadius.small)
                    }
                }
            }
            .padding(Spacing.xs)
            .background(Color.white.opacity(0.1))
            .cornerRadius(CornerRadius.small)
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
    }

    // MARK: - Tab Content

    @ViewBuilder
    private var tabContent: some View {
        switch viewModel.selectedTab {
        case .overview:
            WikiOverviewTab(viewModel: viewModel)
        case .modules:
            WikiModuleListView(viewModel: viewModel)
        case .decisions:
            WikiDecisionsView(viewModel: viewModel)
        case .roadmap:
            WikiRoadmapView(viewModel: viewModel)
        case .diagrams:
            WikiDiagramListView(viewModel: viewModel)
        }
    }

    // MARK: - Loading

    private var loadingView: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .white))
            Text("Loading wiki...")
                .foregroundColor(.white.opacity(0.6))
            Spacer()
        }
    }
}

// MARK: - Overview Tab

struct WikiOverviewTab: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.lg) {
                if let article = viewModel.overviewArticle, article.isGenerated {
                    // Generated overview
                    WikiArticleContentView(article: article)
                } else {
                    // Empty state with generate button
                    emptyState
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.bottom, Spacing.xxl)
        }
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
                .frame(height: Spacing.xxl)

            Image(systemName: "building.columns")
                .font(.system(size: 48))
                .foregroundColor(.white.opacity(0.2))

            VStack(spacing: Spacing.sm) {
                Text("Architecture Overview")
                    .font(.headline)
                    .foregroundColor(.white.opacity(0.6))

                Text("Generate an AI-written narrative walkthrough of how Hestia works.")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.4))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }

            Button {
                Task {
                    await viewModel.generateArticle(type: "overview")
                }
            } label: {
                HStack(spacing: Spacing.sm) {
                    if viewModel.isGenerating {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "sparkles")
                    }
                    Text("Generate Overview (~$0.15)")
                }
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.white)
                .padding(.horizontal, Spacing.lg)
                .padding(.vertical, Spacing.sm)
                .background(Color.white.opacity(0.2))
                .cornerRadius(CornerRadius.small)
            }
            .disabled(viewModel.isGenerating)
        }
    }
}

// MARK: - Article Content View (reusable markdown renderer)

struct WikiArticleContentView: View {
    let article: WikiArticle

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Header
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(article.title)
                    .font(.greeting)
                    .foregroundColor(.white)

                if !article.subtitle.isEmpty {
                    Text(article.subtitle)
                        .font(.subheading)
                        .foregroundColor(.white.opacity(0.6))
                }

                // Meta badges
                HStack(spacing: Spacing.sm) {
                    Label(article.readTimeBadge, systemImage: "clock")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.4))

                    if article.isGenerated, let _ = article.generatedAt {
                        Label("AI Generated", systemImage: "sparkles")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))
                    }

                    if article.isStatic {
                        Label("From Docs", systemImage: "doc.text")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))
                    }
                }
                .padding(.top, Spacing.xs)
            }
            .padding(.bottom, Spacing.sm)

            // Content body
            Text(markdownAttributed(article.content))
                .font(.messageBody)
                .foregroundColor(.white.opacity(0.85))
                .textSelection(.enabled)
        }
        .padding(Spacing.lg)
    }

    private func markdownAttributed(_ markdown: String) -> AttributedString {
        do {
            return try AttributedString(markdown: markdown, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))
        } catch {
            return AttributedString(markdown)
        }
    }
}

// MARK: - Preview

struct WikiView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiView()
                .environmentObject(AppState())
        }
    }
}
