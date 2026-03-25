import SwiftUI
import HestiaShared

// MARK: - External Sub-Tab

enum ExternalSubTab: String, CaseIterable {
    case trading
    case news
    case investigations

    var label: String {
        switch self {
        case .trading: return "Trading"
        case .news: return "News"
        case .investigations: return "Investigations"
        }
    }

    var icon: String {
        switch self {
        case .trading: return "chart.line.uptrend.xyaxis"
        case .news: return "newspaper"
        case .investigations: return "magnifyingglass.circle"
        }
    }
}

// MARK: - External Activity Tab

struct ExternalActivityView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    @StateObject private var tradingViewModel = MacTradingViewModel()
    @State private var selectedSubTab: ExternalSubTab = .news

    var body: some View {
        VStack(spacing: MacSpacing.md) {
            // Sub-tab pills — filter-pill style (audit recommendation: lighter than segmented)
            subTabBar
                .padding(.top, MacSpacing.md)

            // Sub-tab content
            switch selectedSubTab {
            case .trading:
                TradingMonitorView(viewModel: tradingViewModel)
            case .news:
                NewsFeedListView(viewModel: viewModel)
            case .investigations:
                InvestigationsListView(investigations: viewModel.investigations)
            }
        }
    }

    // MARK: - Sub-Tab Pills

    private var subTabBar: some View {
        HStack(spacing: MacSpacing.sm) {
            ForEach(ExternalSubTab.allCases, id: \.self) { tab in
                subTabPill(tab)
            }
            Spacer()
        }
        .padding(.horizontal, MacSpacing.sm)
    }

    private func subTabPill(_ tab: ExternalSubTab) -> some View {
        let isActive = selectedSubTab == tab

        return Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                selectedSubTab = tab
            }
        } label: {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: tab.icon)
                    .font(MacTypography.label)
                Text(tab.label)
                    .font(MacTypography.smallMedium)

                // News unread badge
                if tab == .news && viewModel.externalUnreadCount > 0 {
                    Text("\(viewModel.externalUnreadCount)")
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(MacColors.amberBright)
                        .clipShape(Capsule())
                }
            }
            .foregroundStyle(isActive ? MacColors.amberAccent : MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.xs + 1)
            .background(isActive ? MacColors.amberAccent.opacity(0.13) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.hestia)
        .accessibilityLabel("\(tab.label) feed")
        .accessibilityAddTraits(isActive ? .isSelected : [])
    }
}
