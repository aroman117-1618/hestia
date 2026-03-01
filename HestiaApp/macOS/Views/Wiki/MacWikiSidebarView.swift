import SwiftUI
import HestiaShared

struct MacWikiSidebarView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Tab buttons (vertical)
            tabButtons
                .padding(.horizontal, MacSpacing.sm)
                .padding(.top, MacSpacing.lg)
                .padding(.bottom, MacSpacing.md)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            // Article list
            articleList
        }
    }

    // MARK: - Tab Buttons

    private var tabButtons: some View {
        VStack(spacing: 4) {
            ForEach(WikiViewModel.Tab.allCases) { tab in
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        viewModel.selectedTab = tab
                    }
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: tab.iconName)
                            .font(.system(size: 13))
                            .frame(width: 20)
                        Text(tab.rawValue)
                            .font(.system(size: 13, weight: viewModel.selectedTab == tab ? .semibold : .regular))
                        Spacer()
                        Text("\(articleCount(for: tab))")
                            .font(.system(size: 11))
                            .foregroundStyle(MacColors.textFaint)
                    }
                    .foregroundStyle(viewModel.selectedTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.vertical, 6)
                    .background(
                        viewModel.selectedTab == tab
                            ? MacColors.activeTabBackground
                            : Color.clear
                    )
                    .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Article List

    private var articleList: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(articlesForSelectedTab) { article in
                    MacWikiArticleRow(
                        article: article,
                        isSelected: viewModel.selectedTab == tabForArticle(article)
                    )
                }

                if articlesForSelectedTab.isEmpty && !viewModel.isLoading {
                    if let error = viewModel.errorMessage {
                        errorState(error)
                    } else {
                        emptyState
                    }
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.top, MacSpacing.sm)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 28))
                .foregroundStyle(MacColors.textFaint)
            Text("No articles yet")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
            Text("Use the toolbar to generate or refresh content")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
        }
        .padding(.top, MacSpacing.xxxl)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 28))
                .foregroundStyle(MacColors.healthRed)
            Text(message)
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
                .multilineTextAlignment(.center)
            Button {
                Task { await viewModel.loadArticles() }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.clockwise")
                    Text("Retry")
                }
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, 4)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.plain)
        }
        .padding(.top, MacSpacing.xxxl)
    }

    // MARK: - Helpers

    private var articlesForSelectedTab: [WikiArticle] {
        switch viewModel.selectedTab {
        case .overview:
            if let overview = viewModel.overviewArticle {
                return [overview]
            }
            return []
        case .modules:
            return viewModel.moduleArticles
        case .decisions:
            return viewModel.decisionArticles
        case .roadmap:
            if let roadmap = viewModel.roadmapArticle {
                return [roadmap]
            }
            return []
        case .diagrams:
            return viewModel.diagramArticles
        }
    }

    private func articleCount(for tab: WikiViewModel.Tab) -> Int {
        switch tab {
        case .overview: return viewModel.overviewArticle != nil ? 1 : 0
        case .modules: return viewModel.moduleArticles.count
        case .decisions: return viewModel.decisionArticles.count
        case .roadmap: return viewModel.roadmapArticle != nil ? 1 : 0
        case .diagrams: return viewModel.diagramArticles.count
        }
    }

    private func tabForArticle(_ article: WikiArticle) -> WikiViewModel.Tab {
        switch article.type {
        case .overview: return .overview
        case .module: return .modules
        case .decision: return .decisions
        case .roadmap: return .roadmap
        case .diagram: return .diagrams
        }
    }
}
