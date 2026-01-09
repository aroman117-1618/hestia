import SwiftUI
import CoreData

/// Command Center view with modular widgets: Calendar, Orders, Neural Net
struct CommandCenterView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.managedObjectContext) private var viewContext
    @StateObject private var viewModel = CommandCenterViewModel()

    var body: some View {
        ZStack {
            // Background
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    // Header
                    header

                    // Module 1: Calendar or Empty State
                    calendarModule

                    // Tab selector (Orders / Alerts)
                    tabSelector

                    // Content based on selected tab
                    switch viewModel.selectedTab {
                    case .orders:
                        OrdersWidget(
                            orders: $viewModel.orders,
                            isFormExpanded: $viewModel.isOrderFormExpanded,
                            onToggleStatus: viewModel.toggleOrderStatus,
                            onDelete: viewModel.deleteOrder,
                            onAddOrder: viewModel.addOrder
                        )
                    case .alerts:
                        AlertsWidget(
                            executions: viewModel.recentExecutions,
                            orders: viewModel.orders
                        )
                    case .memory:
                        MemoryWidget()
                    }

                    // Module 3: Neural Net Placeholder
                    neuralNetPlaceholder

                    Spacer()
                        .frame(height: Spacing.xl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
        }
        .onAppear {
            Task {
                await viewModel.refresh()
            }
        }
        .onDisappear {
            viewModel.stopRefresh()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Hello, Andrew")
                    .greetingStyle()

                if viewModel.alertCount > 0 {
                    Text("You have \(viewModel.alertCount) alert\(viewModel.alertCount == 1 ? "" : "s")")
                        .subheadingStyle()
                } else {
                    Text("All systems running smoothly")
                        .subheadingStyle()
                }
            }

            Spacer()

            // Avatar
            if let image = appState.currentMode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
                    .frame(width: Size.Avatar.small, height: Size.Avatar.small)
                    .clipShape(Circle())
            } else {
                Circle()
                    .fill(Color.white.opacity(0.2))
                    .frame(width: Size.Avatar.small, height: Size.Avatar.small)
                    .overlay(
                        Text(appState.currentMode.displayName.prefix(1))
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(.white)
                    )
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Calendar Module

    @ViewBuilder
    private var calendarModule: some View {
        if viewModel.isCalendarLoading {
            NextMeetingCard(event: nil, isLoading: true)
        } else if let event = viewModel.nextEvent {
            NextMeetingCard(event: event, isLoading: false)
        } else if viewModel.isCalendarAuthorized {
            // No events - show empty state with quote
            CalendarEmptyStateView()
        } else {
            // Calendar access denied
            calendarAccessDeniedCard
        }
    }

    private var calendarAccessDeniedCard: some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: "calendar.badge.exclamationmark")
                .font(.system(size: 32))
                .foregroundColor(.warningYellow)

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Calendar Access Required")
                    .font(.headline)
                    .foregroundColor(.white)

                Text("Enable calendar access in Settings to see your upcoming events")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()
        }
        .padding(Spacing.md)
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Tab Selector

    private var tabSelector: some View {
        HStack(spacing: 0) {
            ForEach(CommandCenterViewModel.CommandTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(.hestiaQuick) {
                        viewModel.selectedTab = tab
                    }
                } label: {
                    HStack(spacing: Spacing.xs) {
                        Text(tab.rawValue)
                            .font(.subheadline.weight(.semibold))

                        // Show alert badge on Alerts tab
                        if tab == .alerts && viewModel.alertCount > 0 {
                            Text("\(viewModel.alertCount)")
                                .font(.caption2.weight(.bold))
                                .foregroundColor(.white)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.errorRed)
                                .cornerRadius(8)
                        }

                        // Show pending count badge on Memory tab
                        if tab == .memory && viewModel.pendingMemoryCount > 0 {
                            Text("\(viewModel.pendingMemoryCount)")
                                .font(.caption2.weight(.bold))
                                .foregroundColor(.white)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.warningYellow)
                                .cornerRadius(8)
                        }
                    }
                    .foregroundColor(viewModel.selectedTab == tab ? .white : .white.opacity(0.6))
                    .padding(.vertical, Spacing.sm)
                    .padding(.horizontal, Spacing.md)
                    .background(
                        viewModel.selectedTab == tab ?
                        Color.white.opacity(0.2) :
                        Color.clear
                    )
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
        .padding(Spacing.xs)
        .background(Color.white.opacity(0.1))
        .cornerRadius(CornerRadius.small)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Neural Net Placeholder

    private var neuralNetPlaceholder: some View {
        VStack(spacing: Spacing.md) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 40))
                .foregroundColor(.white.opacity(0.3))

            VStack(spacing: Spacing.xs) {
                Text("Neural Net")
                    .font(.headline)
                    .foregroundColor(.white.opacity(0.7))

                Text("Coming Soon")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.4))

                Text("Second half of 2026")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.3))
            }
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.white.opacity(0.03))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }
}

// MARK: - Preview

struct CommandCenterView_Previews: PreviewProvider {
    static var previews: some View {
        CommandCenterView()
            .environmentObject(AppState())
            .environment(\.managedObjectContext, PersistenceController.preview.viewContext)
    }
}
