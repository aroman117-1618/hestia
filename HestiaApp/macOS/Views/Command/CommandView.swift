import SwiftUI
import HestiaShared

struct CommandView: View {
    @StateObject private var viewModel = MacCommandCenterViewModel()
    @EnvironmentObject var appState: AppState

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                // Hero greeting + progress rings
                HeroSection(viewModel: viewModel)

                // Stat cards row
                StatCardsRow(viewModel: viewModel)

                // Calendar + Orders side by side
                HStack(alignment: .top, spacing: MacSpacing.lg) {
                    CalendarWeekStrip(events: viewModel.calendarEvents)
                        .frame(maxWidth: .infinity)

                    OrdersPanel(orders: viewModel.orders)
                        .frame(width: 320)
                }

                // Activity feed
                ActivityFeed(orders: viewModel.orders, newsfeedItems: viewModel.newsfeedItems)
            }
            .padding(MacSpacing.xxl)
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadAllData()
        }
    }
}
