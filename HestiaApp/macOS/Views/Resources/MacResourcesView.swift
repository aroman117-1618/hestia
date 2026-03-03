import SwiftUI
import HestiaShared

struct MacResourcesView: View {
    @State private var selectedTab: ResourceTab = .llms

    enum ResourceTab: String, CaseIterable {
        case llms = "LLMs"
        case integrations = "Integrations"
        case devices = "Devices"
        case mcps = "MCPs"

        var iconName: String {
            switch self {
            case .llms: return "cloud"
            case .integrations: return "link"
            case .devices: return "laptopcomputer.and.iphone"
            case .mcps: return "cpu"
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Tab bar
            tabBar
                .padding(.horizontal, MacSpacing.xl)
                .padding(.top, MacSpacing.lg)
                .padding(.bottom, MacSpacing.sm)

            // Content
            Group {
                switch selectedTab {
                case .llms:
                    MacCloudSettingsView()
                case .integrations:
                    MacIntegrationsView()
                case .devices:
                    MacDeviceManagementView()
                case .mcps:
                    MacMCPPlaceholderView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(MacColors.windowBackground)
    }

    // MARK: - Tab Bar

    private var tabBar: some View {
        HStack(spacing: MacSpacing.md) {
            ForEach(ResourceTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        selectedTab = tab
                    }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: tab.iconName)
                            .font(.system(size: 13))
                        Text(tab.rawValue)
                            .font(.system(size: 13, weight: selectedTab == tab ? .semibold : .regular))
                    }
                    .foregroundStyle(selectedTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, 6)
                    .background(
                        selectedTab == tab
                            ? MacColors.activeTabBackground
                            : Color.clear
                    )
                    .cornerRadius(MacCornerRadius.tab)
                }
                .buttonStyle(.hestia)
            }

            Spacer()
        }
    }
}
