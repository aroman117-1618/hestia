import SwiftUI
import HestiaShared

struct CommandView: View {
    @StateObject private var viewModel = MacCommandCenterViewModel()
    @EnvironmentObject var appState: AppState

    var body: some View {
        GeometryReader { geo in
            let isCompact = geo.size.width < 700

            ScrollView {
                VStack(spacing: MacSpacing.lg) {
                    // Hero greeting + progress rings
                    HeroSection(viewModel: viewModel, isCompact: isCompact)

                    // Stat cards row
                    StatCardsRow(viewModel: viewModel, isCompact: isCompact)

                    // Calendar + Orders — side by side or stacked
                    if isCompact {
                        VStack(spacing: MacSpacing.lg) {
                            CalendarWeekStrip(events: viewModel.calendarEvents)
                            OrdersPanel(orders: viewModel.orders)
                        }
                    } else {
                        HStack(alignment: .top, spacing: MacSpacing.lg) {
                            CalendarWeekStrip(events: viewModel.calendarEvents)
                                .frame(maxWidth: .infinity)
                            OrdersPanel(orders: viewModel.orders)
                                .frame(minWidth: 280, idealWidth: 320, maxWidth: 360)
                        }
                    }

                    // Activity feed
                    ActivityFeed(orders: viewModel.orders, newsfeedItems: viewModel.newsfeedItems, isCompact: isCompact)
                }
                .padding(MacSpacing.xxl)
            }
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadAllData()
        }
    }
}
