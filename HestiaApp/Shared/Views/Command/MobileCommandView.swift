import SwiftUI
import HestiaShared

/// Card-based mobile command dashboard — view + critical actions.
struct MobileCommandView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @EnvironmentObject var authService: AuthService
    @StateObject private var viewModel = MobileCommandViewModel()

    var body: some View {
        NavigationView {
            ZStack {
                GradientBackground(mode: appState.currentMode)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Spacing.md) {
                        // Status Card
                        statusCard

                        // Trading Card
                        tradingCard

                        // Orders Card
                        ordersCard

                        // Newsfeed Card
                        newsfeedCard

                        // Quick Actions
                        quickActionsCard
                    }
                    .padding(.horizontal, Spacing.md)
                    .padding(.top, Spacing.sm)
                    .padding(.bottom, Spacing.xl)
                }
                .refreshable {
                    await viewModel.loadAll()
                }
            }
            .navigationTitle("Command")
            .navigationBarTitleDisplayMode(.large)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .onAppear {
            if apiClientProvider.isReady {
                viewModel.configure(client: apiClientProvider.client)
                Task { await viewModel.loadAll() }
            }
        }
        .onChange(of: apiClientProvider.isReady) { isReady in
            if isReady {
                viewModel.configure(client: apiClientProvider.client)
                Task { await viewModel.loadAll() }
            }
        }
    }

    // MARK: - Status Card

    private var statusCard: some View {
        HestiaCard(label: "STATUS") {
            HStack(spacing: Spacing.lg) {
                statusMetric(
                    value: "\(viewModel.summary?.activeBots ?? 0)",
                    label: "Bots"
                )
                statusMetric(
                    value: formatPnl(viewModel.summary?.totalPnl ?? 0),
                    label: "24h P&L"
                )
                statusMetric(
                    value: "\(viewModel.summary?.totalTrades ?? 0)",
                    label: "Fills"
                )
                Spacer()
                if let summary = viewModel.summary {
                    HestiaStatusBadge(
                        text: summary.killSwitchActive ? "Kill Active" : "Healthy",
                        status: summary.killSwitchActive ? .error : .healthy
                    )
                }
            }
        }
    }

    // MARK: - Trading Card

    private var tradingCard: some View {
        HestiaCard(label: "TRADING") {
            VStack(spacing: Spacing.sm) {
                if viewModel.bots.isEmpty && !viewModel.failedSections.contains("bots") {
                    Text("No active bots")
                        .font(.caption)
                        .foregroundColor(.textTertiary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.md)
                } else {
                    ForEach(viewModel.bots) { bot in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(bot.name)
                                    .font(.body.weight(.medium))
                                    .foregroundColor(.textPrimary)
                                Text(bot.pair)
                                    .font(.caption)
                                    .foregroundColor(.textSecondary)
                            }
                            Spacer()
                            HestiaStatusBadge(
                                text: bot.status.capitalized,
                                status: bot.status == "running" ? .healthy : .neutral
                            )
                        }
                        .padding(.vertical, Spacing.xs)
                    }
                }

                Divider().background(Color.iosCardBorder)

                // Kill Switch
                Button {
                    viewModel.killSwitchConfirmation = true
                } label: {
                    HStack {
                        Image(systemName: viewModel.riskStatus?.killSwitch.active == true
                              ? "play.circle.fill" : "xmark.octagon.fill")
                        Text(viewModel.riskStatus?.killSwitch.active == true
                             ? "Reactivate Trading" : "Kill Switch")
                            .font(.body.weight(.semibold))
                    }
                    .foregroundColor(viewModel.riskStatus?.killSwitch.active == true ? .healthyGreen : .errorRed)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.sm)
                }
                .alert("Confirm", isPresented: $viewModel.killSwitchConfirmation) {
                    Button("Cancel", role: .cancel) {}
                    Button(
                        viewModel.riskStatus?.killSwitch.active == true ? "Reactivate" : "Kill All Trading",
                        role: viewModel.riskStatus?.killSwitch.active == true ? nil : .destructive
                    ) {
                        Task { await viewModel.toggleKillSwitch() }
                    }
                } message: {
                    Text(viewModel.riskStatus?.killSwitch.active == true
                         ? "Reactivate all trading bots?"
                         : "This will immediately stop all trading activity.")
                }
            }
        }
    }

    // MARK: - Orders Card

    private var ordersCard: some View {
        HestiaCard(label: "ORDERS") {
            if viewModel.workflows.isEmpty && !viewModel.failedSections.contains("workflows") {
                Text("No active orders")
                    .font(.caption)
                    .foregroundColor(.textTertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
            } else {
                VStack(spacing: Spacing.sm) {
                    ForEach(viewModel.workflows.prefix(3)) { workflow in
                        HStack {
                            Text(workflow.name)
                                .font(.body)
                                .foregroundColor(.textPrimary)
                                .lineLimit(1)
                            Spacer()
                            HestiaStatusBadge(
                                text: workflow.status.capitalized,
                                status: statusFor(workflow.status)
                            )
                        }
                    }
                    if viewModel.workflows.count > 3 {
                        Text("+\(viewModel.workflows.count - 3) more")
                            .font(.caption)
                            .foregroundColor(.textTertiary)
                    }
                }
            }
        }
    }

    // MARK: - Newsfeed Card

    private var newsfeedCard: some View {
        HestiaCard(label: "NEWSFEED") {
            if viewModel.newsfeedItems.isEmpty && !viewModel.failedSections.contains("newsfeed") {
                Text("No recent items")
                    .font(.caption)
                    .foregroundColor(.textTertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
            } else {
                VStack(spacing: Spacing.sm) {
                    ForEach(viewModel.newsfeedItems.prefix(3)) { item in
                        HStack(alignment: .top, spacing: Spacing.sm) {
                            if item.isRead != true {
                                Circle()
                                    .fill(Color.systemBlue)
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 6)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.title)
                                    .font(.body)
                                    .foregroundColor(.textPrimary)
                                    .lineLimit(1)
                                if let summary = item.summary {
                                    Text(summary)
                                        .font(.caption)
                                        .foregroundColor(.textSecondary)
                                        .lineLimit(2)
                                }
                            }
                            Spacer()
                        }
                    }
                }
            }
        }
    }

    // MARK: - Quick Actions

    private var quickActionsCard: some View {
        HestiaCard(label: "QUICK ACTIONS") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Spacing.sm) {
                HestiaPillButton(title: "Cloud Mode", icon: "cloud.fill", tint: .accent) {
                    Task {
                        _ = try? await apiClientProvider.client.cycleCloudState()
                    }
                }
                HestiaPillButton(title: "Investigate", icon: "magnifyingglass", tint: .accent) {
                    // TODO: Navigate to investigate sheet
                }
                HestiaPillButton(title: "Journal", icon: "book.fill", tint: .accent) {
                    // TODO: Switch to chat tab in journal mode
                }
                HestiaPillButton(title: "Lock", icon: "lock.fill", tint: .errorRed) {
                    authService.lock()
                }
            }
        }
    }

    // MARK: - Helpers

    private func statusMetric(value: String, label: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundColor(.textPrimary)
            Text(label)
                .font(.caption2)
                .foregroundColor(.textSecondary)
        }
    }

    private func formatPnl(_ value: Double) -> String {
        let prefix = value >= 0 ? "+" : ""
        return "\(prefix)$\(String(format: "%.2f", value))"
    }

    private func statusFor(_ status: String) -> HestiaStatusBadge.Status {
        switch status.lowercased() {
        case "active", "running": return .healthy
        case "paused", "pending": return .warning
        case "failed", "error": return .error
        default: return .neutral
        }
    }
}
