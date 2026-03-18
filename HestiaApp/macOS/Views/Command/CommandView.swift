import SwiftUI
import HestiaShared

struct CommandView: View {
    @StateObject private var viewModel = MacCommandCenterViewModel()
    @EnvironmentObject var appState: AppState
    @Environment(\.layoutMode) private var layoutMode

    var body: some View {
        VStack(spacing: 0) {
            // Top section: hero greeting + progress rings
            HeroSection(viewModel: viewModel)
                .padding(.horizontal, MacSpacing.xxl)
                .padding(.top, MacSpacing.xxl)
                .padding(.bottom, MacSpacing.lg)

            MacColors.divider
                .frame(height: 1)

            // Bottom section: tabbed activity feed
            ActivityFeedView(viewModel: viewModel)
                .padding(.horizontal, MacSpacing.xxl)
                .padding(.bottom, MacSpacing.lg)
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadAllData()
        }
    }
}
