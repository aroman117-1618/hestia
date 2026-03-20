import SwiftUI
import HestiaShared

// MARK: - Activity Feed Tab Category

enum ActivityFeedTab: String, CaseIterable {
    case `internal`
    case external
    case system

    var label: String {
        switch self {
        case .system: return "System"
        case .internal: return "Internal"
        case .external: return "External"
        }
    }

    var icon: String {
        switch self {
        case .system: return "gearshape.2"
        case .internal: return "person"
        case .external: return "globe"
        }
    }
}

// MARK: - Activity Feed View (3-tab container)

struct ActivityFeedView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    @State private var selectedTab: ActivityFeedTab = .internal

    var body: some View {
        VStack(spacing: 0) {
            // Segmented toggle — matches Research view pattern
            tabBar
                .padding(.top, MacSpacing.xl)
                .padding(.bottom, MacSpacing.md)

            // Tab content
            switch selectedTab {
            case .internal:
                InternalActivityView(viewModel: viewModel)
            case .external:
                ExternalActivityView(viewModel: viewModel)
            case .system:
                SystemActivityView(viewModel: viewModel)
            }
        }
        .background(MacColors.windowBackground)
        .onReceive(NotificationCenter.default.publisher(for: .activityTabSwitch)) { notification in
            if let rawValue = notification.userInfo?["tab"] as? String,
               let tab = ActivityFeedTab(rawValue: rawValue) {
                withAnimation(.easeInOut(duration: 0.2)) {
                    selectedTab = tab
                }
            }
        }
    }

    // MARK: - Tab Bar

    private var tabBar: some View {
        HStack(spacing: 2) {
            ForEach(ActivityFeedTab.allCases, id: \.self) { tab in
                tabButton(tab)
            }
        }
        .padding(MacSpacing.xs)
        .background(MacColors.textPrimary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
    }

    private func tabButton(_ tab: ActivityFeedTab) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                selectedTab = tab
            }
        } label: {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: tab.icon)
                    .font(.system(size: 14))
                Text(tab.label)
                    .font(.system(size: 13, weight: .medium))

                // Unread badge on External tab
                if tab == .external && viewModel.unreadCount > 0 {
                    Text("\(viewModel.unreadCount)")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1)
                        .background(MacColors.amberBright)
                        .clipShape(Capsule())
                }
            }
            .foregroundStyle(selectedTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(selectedTab == tab ? MacColors.amberAccent.opacity(0.15) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
        .buttonStyle(.hestia)
        .accessibilityLabel("\(tab.label) activity")
        .accessibilityAddTraits(selectedTab == tab ? .isSelected : [])
    }
}
