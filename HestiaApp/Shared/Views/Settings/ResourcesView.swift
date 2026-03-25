import SwiftUI
import HestiaShared

/// Resources hub — LLMs, Integrations, and MCPs in a tabbed view
struct ResourcesView: View {
    @StateObject private var viewModel = ResourcesViewModel()

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                // Tab selector
                tabSelector

                // Content based on selected tab
                switch viewModel.selectedTab {
                case .llms:
                    CloudSettingsView()
                case .integrations:
                    IntegrationsView()
                case .mcps:
                    placeholderTab(
                        icon: "cpu",
                        title: "MCP Servers",
                        subtitle: "Model Context Protocol server management will appear here.",
                        comingSoon: "Coming Soon"
                    )
                }
            }
        }
        .navigationTitle("Resources")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Tab Selector

    private var tabSelector: some View {
        HStack(spacing: 0) {
            ForEach(ResourcesViewModel.Tab.allCases) { tab in
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
                    .foregroundColor(viewModel.selectedTab == tab ? .textPrimary : .textSecondary)
                    .padding(.vertical, Spacing.sm)
                    .padding(.horizontal, Spacing.md)
                    .background(
                        viewModel.selectedTab == tab ?
                        Color.bgOverlay :
                        Color.clear
                    )
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
        .padding(Spacing.xs)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.small)
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
    }

    // MARK: - Placeholder Tab

    private func placeholderTab(icon: String, title: String, subtitle: String, comingSoon: String) -> some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            VStack(spacing: Spacing.sm) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.textSecondary)

                Text(subtitle)
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)

                Text(comingSoon)
                    .font(.caption)
                    .foregroundColor(.textTertiary)
                    .padding(.top, Spacing.xs)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Preview

struct ResourcesView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ResourcesView()
        }
    }
}
