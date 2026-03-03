import SwiftUI
import HestiaShared

struct MacWikiSidebarView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        VStack(spacing: 0) {
            tabButtons
                .padding(.horizontal, MacSpacing.sm)
                .padding(.top, MacSpacing.lg)
                .padding(.bottom, MacSpacing.md)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            articleList

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            pinnedRoadmapRow
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, MacSpacing.sm)

            if viewModel.lastUpdatedText != nil {
                cacheTimestampFooter
            }
        }
    }

    // MARK: - Cache Timestamp Footer

    private var cacheTimestampFooter: some View {
        TimelineView(.periodic(from: .now, by: 60)) { _ in
            if let text = viewModel.lastUpdatedText {
                Text(text)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, MacSpacing.xs)
            }
        }
    }

    // MARK: - Tab Buttons

    private var tabButtons: some View {
        VStack(spacing: 4) {
            ForEach(WikiTabCategory.allCases) { tab in
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
                        viewModel.selectedTab == tab && !viewModel.showingRoadmap
                            ? MacColors.activeTabBackground
                            : Color.clear
                    )
                    .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.hestia)
                .hoverCursor(.pointingHand)
            }
        }
    }

    // MARK: - Article List

    private var articleList: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(viewModel.currentTabArticles) { article in
                    MacWikiArticleRow(
                        article: article,
                        isSelected: viewModel.selectedArticleId == article.id
                    )
                    .contentShape(Rectangle())
                    .onTapGesture {
                        viewModel.selectArticle(article)
                    }
                }

                if viewModel.currentTabArticles.isEmpty && !viewModel.isLoading {
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

    // MARK: - Pinned Roadmap Row

    private var pinnedRoadmapRow: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                viewModel.showingRoadmap = true
                viewModel.selectedArticleId = nil
            }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "flag.checkered")
                    .font(.system(size: 13))
                    .frame(width: 20)
                Text("Roadmap")
                    .font(.system(size: 13, weight: viewModel.showingRoadmap ? .semibold : .regular))
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }
            .foregroundStyle(viewModel.showingRoadmap ? MacColors.amberAccent : MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 6)
            .background(
                viewModel.showingRoadmap
                    ? MacColors.activeTabBackground
                    : Color.clear
            )
            .cornerRadius(MacCornerRadius.treeItem)
        }
        .buttonStyle(.hestia)
        .accessibilityLabel("Roadmap")
        .hoverCursor(.pointingHand)
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
            .buttonStyle(.hestia)
        }
        .padding(.top, MacSpacing.xxxl)
    }

    // MARK: - Helpers

    private func articleCount(for tab: WikiTabCategory) -> Int {
        switch tab {
        case .overview:
            return viewModel.overviewArticle != nil ? 1 : 0
        case .core, .skills, .memory, .resources:
            let modules = WikiTabCategory.modules(for: tab)
            return viewModel.moduleArticles.filter { article in
                modules.contains(article.moduleName ?? "")
            }.count
        }
    }
}
