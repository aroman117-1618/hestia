import SwiftUI
import HestiaShared

struct CommandView: View {
    @StateObject private var viewModel = MacCommandCenterViewModel()
    @Environment(WorkspaceState.self) private var workspace
    @Environment(ErrorState.self) private var errorState

    var body: some View {
        VStack(spacing: 0) {
            // Hero section: avatar + wavelength left, stats right
            HeroSection(viewModel: viewModel)

            MacColors.divider
                .frame(height: 0.5)

            // Sub-tab bar
            subTabBar

            MacColors.divider
                .frame(height: 0.5)

            // Sub-tab content (lazy — only active tab renders)
            Group {
                switch workspace.commandSubTab {
                case .internal:
                    InternalTabView()
                case .newsfeed:
                    NewsfeedTabView()
                case .systemAlerts:
                    SystemAlertsTabView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(MacColors.windowBackground)
        .task {
            viewModel.configure(errorState: errorState)
            await viewModel.loadAllData()
        }
        .onReceive(NotificationCenter.default.publisher(for: .hestiaServerReconnected)) { _ in
            Task { await viewModel.loadAllData() }
        }
    }

    // MARK: - Sub-Tab Bar

    private var subTabBar: some View {
        HStack(spacing: 0) {
            ForEach(WorkspaceState.CommandSubTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        workspace.commandSubTab = tab
                    }
                } label: {
                    VStack(spacing: 0) {
                        Text(tab.rawValue)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(workspace.commandSubTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
                            .padding(.horizontal, MacSpacing.lg)
                            .padding(.vertical, 10)

                        Rectangle()
                            .fill(workspace.commandSubTab == tab ? MacColors.amberAccent : Color.clear)
                            .frame(height: 2)
                    }
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.leading, MacSpacing.xxl)
    }
}
