import SwiftUI
import HestiaShared

// MARK: - Trading Monitor (Sprint 26 — live data)

struct TradingMonitorView: View {
    @ObservedObject var viewModel: MacTradingViewModel

    @State private var firstRunStrategy = "mean_reversion"
    @State private var firstRunPair = "BTC-USD"
    @State private var firstRunCapital = 25.0

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                autonomousTradingToggle
                portfolioSnapshotCard
                if !viewModel.decisionFeed.isEmpty {
                    decisionFeedSection
                }
                activePositionsSection
                recentTradesSection
                watchlistSection
                riskStatusCard
                killSwitchButton
            }
            .padding(.top, MacSpacing.lg)
        }
        .task {
            await viewModel.loadAllData()
            viewModel.startPeriodicRefresh()
        }
        .onDisappear {
            viewModel.cleanup()
        }
        .sheet(isPresented: $viewModel.showFirstRunModal) {
            firstRunConfirmationModal
        }
    }

    // MARK: - Autonomous Trading Toggle

    private var autonomousTradingToggle: some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: viewModel.autonomousTradingEnabled ? "bolt.circle.fill" : "bolt.circle")
                .font(MacTypography.pageTitle)
                .foregroundStyle(viewModel.autonomousTradingEnabled ? MacColors.healthGreen : MacColors.textSecondary)

            VStack(alignment: .leading, spacing: 2) {
                Text("Autonomous Trading")
                    .font(MacTypography.bodyMedium)
                    .foregroundStyle(MacColors.textPrimary)
                Text(viewModel.autonomousTradingEnabled ? "Active — Hestia is managing your trades" : "Disabled — tap to enable")
                    .font(MacTypography.caption)
                    .foregroundStyle(viewModel.autonomousTradingEnabled ? MacColors.healthGreen : MacColors.textFaint)
            }

            Spacer()

            Toggle("", isOn: Binding(
                get: { viewModel.autonomousTradingEnabled },
                set: { _ in viewModel.toggleAutonomousTrading() }
            ))
            .toggleStyle(.switch)
            .tint(MacColors.healthGreen)
            .labelsHidden()
        }
        .padding(MacSpacing.xl)
        .background(
            viewModel.autonomousTradingEnabled
                ? MacColors.healthGreen.opacity(0.06)
                : MacColors.panelBackground
        )
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(
                    viewModel.autonomousTradingEnabled
                        ? MacColors.healthGreen.opacity(0.2)
                        : MacColors.cardBorder,
                    lineWidth: 1
                )
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Decision Feed

    private var decisionFeedSection: some View {
        CollapsibleSection(
            title: "Live Decision Feed",
            icon: "text.alignleft"
        ) {
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                ForEach(viewModel.decisionFeed.prefix(20)) { entry in
                    HStack(alignment: .top, spacing: MacSpacing.sm) {
                        Text(entry.timeString)
                            .font(MacTypography.code)
                            .foregroundStyle(MacColors.textFaint)
                            .frame(width: 55, alignment: .leading)

                        Image(systemName: entry.sourceIcon)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.amberAccent)
                            .frame(width: 14)

                        Text("[\(entry.source)]")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .foregroundStyle(MacColors.textSecondary)

                        Text(entry.message)
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textPrimary)
                            .lineLimit(2)
                    }
                }
            }
            .padding(.vertical, MacSpacing.xs)
        }
    }

    // MARK: - First-Run Confirmation Modal

    private var firstRunConfirmationModal: some View {
        VStack(spacing: MacSpacing.lg) {
            // Header
            VStack(spacing: MacSpacing.sm) {
                Image(systemName: "bolt.circle.fill")
                    .font(MacTypography.largeValue)
                    .foregroundStyle(MacColors.amberAccent)
                Text("Enable Autonomous Trading")
                    .font(MacTypography.pageTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Text("Hestia will manage trades automatically using the settings below.")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)
                    .multilineTextAlignment(.center)
            }

            // Settings
            VStack(alignment: .leading, spacing: MacSpacing.md) {
                settingRow(label: "Strategy", value: firstRunStrategy == "mean_reversion" ? "Mean Reversion (RSI)" : "Grid Trading")
                settingRow(label: "Pair", value: firstRunPair)
                settingRow(label: "Capital", value: "$\(String(format: "%.0f", firstRunCapital))")
                settingRow(label: "Sizing", value: "Quarter-Kelly (conservative)")
                settingRow(label: "Daily Loss Limit", value: "5%")
                settingRow(label: "Kill Switch", value: "Enabled (persisted)")
            }
            .padding(MacSpacing.lg)
            .background(MacColors.searchInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))

            // Buttons
            HStack(spacing: MacSpacing.md) {
                Button("Cancel") {
                    viewModel.showFirstRunModal = false
                }
                .buttonStyle(.plain)
                .foregroundStyle(MacColors.textSecondary)

                Button {
                    Task {
                        await viewModel.confirmEnableTrading(
                            strategy: firstRunStrategy,
                            pair: firstRunPair,
                            capital: firstRunCapital
                        )
                    }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "bolt.fill")
                        Text("Enable Trading")
                    }
                    .font(MacTypography.bodyMedium)
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.xl)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(MacSpacing.xl * 2)
        .frame(width: 420)
        .background(MacColors.windowBackground)
    }

    private func settingRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(MacTypography.smallMedium)
                .foregroundStyle(MacColors.textSecondary)
            Spacer()
            Text(value)
                .font(MacTypography.code)
                .foregroundStyle(MacColors.textPrimary)
        }
    }

    // MARK: - Portfolio Snapshot

    private var portfolioSnapshotCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                Image(systemName: "chart.pie")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.amberAccent)
                Text("Portfolio Snapshot")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
            }

            HStack(spacing: MacSpacing.lg) {
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Total Value")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    Text(formatCurrency(viewModel.portfolio?.totalValue ?? 0))
                        .font(.system(size: 24, weight: .bold, design: .monospaced))
                        .foregroundStyle(MacColors.textPrimary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: MacSpacing.xs) {
                    Text("24h P&L")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    let pnl = viewModel.portfolio?.dailyPnl ?? 0
                    Text(formatCurrency(pnl))
                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                        .foregroundStyle(pnl >= 0 ? MacColors.healthGreen : MacColors.healthRed)
                }

                VStack(alignment: .trailing, spacing: MacSpacing.xs) {
                    Text("Open Positions")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    Text("\(viewModel.positions.count)")
                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                        .foregroundStyle(MacColors.textPrimary)
                }
            }

            if viewModel.bots.isEmpty {
                statusBanner(
                    icon: "info.circle",
                    text: "No trading bots configured — create a bot to begin",
                    color: MacColors.amberAccent
                )
            }
        }
        .padding(MacSpacing.xl)
        .hestiaPanel()
    }

    // MARK: - Active Positions

    private var activePositionsSection: some View {
        CollapsibleSection(
            title: "Active Positions",
            icon: "arrow.triangle.swap"
        ) {
            if viewModel.positions.isEmpty {
                emptyListState(
                    icon: "chart.bar.xaxis",
                    message: "No active positions",
                    detail: "Positions will appear when trading begins"
                )
            } else {
                VStack(spacing: MacSpacing.sm) {
                    ForEach(Array(viewModel.positions.values), id: \.currency) { position in
                        positionRow(position)
                    }
                }
            }
        }
    }

    private func positionRow(_ position: TradingPositionEntry) -> some View {
        HStack(spacing: MacSpacing.md) {
            Text(position.currency)
                .font(MacTypography.labelMedium)
                .foregroundStyle(MacColors.textPrimary)
            Spacer()
            VStack(alignment: .trailing, spacing: 1) {
                Text(String(format: "%.6f", position.quantity))
                    .font(MacTypography.code)
                    .foregroundStyle(MacColors.textPrimary)
                Text(formatCurrency(position.value))
                    .font(MacTypography.code)
                    .foregroundStyle(MacColors.textSecondary)
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Recent Trades

    private var recentTradesSection: some View {
        CollapsibleSection(
            title: "Recent Trades",
            icon: "list.bullet.rectangle"
        ) {
            if viewModel.trades.isEmpty {
                emptyListState(
                    icon: "arrow.left.arrow.right",
                    message: "No trades yet",
                    detail: "Trades will appear once a bot executes"
                )
            } else {
                VStack(spacing: MacSpacing.sm) {
                    ForEach(viewModel.trades.prefix(10)) { trade in
                        TradeRowView(
                            trade: trade,
                            onFeedback: { rating in
                                Task {
                                    await viewModel.submitFeedback(tradeId: trade.id, rating: rating)
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    // MARK: - Watchlist

    private var watchlistSection: some View {
        CollapsibleSection(
            title: "Watchlist",
            icon: "eye"
        ) {
            if viewModel.watchlist.isEmpty {
                emptyListState(
                    icon: "binoculars",
                    message: "No assets being watched",
                    detail: "Add pairs to your watchlist to monitor"
                )
            } else {
                VStack(spacing: MacSpacing.sm) {
                    ForEach(viewModel.watchlist) { item in
                        watchlistRow(item)
                    }
                }
            }
        }
    }

    private func watchlistRow(_ item: TradingWatchlistItem) -> some View {
        HStack(spacing: MacSpacing.md) {
            Text(item.pair)
                .font(MacTypography.labelMedium)
                .foregroundStyle(MacColors.textPrimary)
            if !item.notes.isEmpty {
                Text(item.notes)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(1)
            }
            Spacer()
            Button {
                Task { await viewModel.removeFromWatchlist(itemId: item.id) }
            } label: {
                Image(systemName: "xmark.circle")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textFaint)
            }
            .buttonStyle(.plain)
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Risk Status

    private var riskStatusCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                Image(systemName: "shield.lefthalf.filled")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.amberAccent)
                Text("Risk Status")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()

                HStack(spacing: MacSpacing.xs) {
                    let breakers = viewModel.riskStatus?.anyBreakerActive ?? false
                    Circle()
                        .fill(breakers ? MacColors.healthRed : MacColors.healthGreen)
                        .frame(width: 10, height: 10)
                    Text(breakers ? "Breaker Active" : "All Clear")
                        .font(MacTypography.caption)
                        .foregroundStyle(breakers ? MacColors.healthRed : MacColors.healthGreen)
                }
            }

            if viewModel.riskStatus == nil {
                statusBanner(icon: "wifi.slash", text: "Risk status unavailable", color: MacColors.textSecondary)
            }
        }
        .padding(MacSpacing.xl)
        .hestiaPanel()
    }

    // MARK: - Kill Switch

    private var killSwitchButton: some View {
        Button {
            Task { await viewModel.toggleKillSwitch() }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "power")
                    .font(MacTypography.bodyMedium)
                Text(viewModel.killSwitchActive ? "Deactivate Kill Switch" : "Emergency Kill Switch")
                    .font(MacTypography.bodyMedium)
            }
            .foregroundStyle(viewModel.killSwitchActive ? MacColors.amberAccent : MacColors.healthRed.opacity(0.7))
            .frame(maxWidth: .infinity)
            .padding(.vertical, MacSpacing.md)
            .background(
                viewModel.killSwitchActive
                    ? MacColors.amberAccent.opacity(0.1)
                    : MacColors.healthRed.opacity(0.06)
            )
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(
                        viewModel.killSwitchActive
                            ? MacColors.amberAccent.opacity(0.3)
                            : MacColors.healthRed.opacity(0.15),
                        lineWidth: 1
                    )
            }
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(
            viewModel.killSwitchActive
                ? "Deactivate emergency kill switch"
                : "Activate emergency kill switch"
        )
    }

    // MARK: - Helpers

    private func emptyListState(icon: String, message: String, detail: String) -> some View {
        VStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(MacTypography.pageTitle)
                .foregroundStyle(MacColors.textSecondary.opacity(0.5))
            Text(message)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            Text(detail)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, MacSpacing.xl)
    }

    private func statusBanner(icon: String, text: String, color: Color) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(MacTypography.smallBody)
            Text(text)
                .font(MacTypography.caption)
        }
        .foregroundStyle(color)
        .padding(MacSpacing.sm)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        return formatter.string(from: NSNumber(value: value)) ?? "$0.00"
    }
}

// MARK: - Trade Row View (expandable with confidence gauge + feedback)

struct TradeRowView: View {
    let trade: TradingTradeResponse
    let onFeedback: (String) -> Void

    @State private var isExpanded = false

    var body: some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: MacSpacing.md) {
                    // Side badge
                    Text(trade.side.uppercased())
                        .font(MacTypography.micro)
                        .foregroundStyle(trade.side == "buy" ? MacColors.healthGreen : MacColors.healthRed)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background((trade.side == "buy" ? MacColors.healthGreen : MacColors.healthRed).opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 4))

                    VStack(alignment: .leading, spacing: 1) {
                        Text(trade.pair)
                            .font(MacTypography.labelMedium)
                            .foregroundStyle(MacColors.textPrimary)
                        Text(String(format: "%.6f @ $%.2f", trade.quantity, trade.price))
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    Spacer()

                    // Confidence gauge
                    if let score = trade.confidenceScore {
                        confidenceGauge(score: score)
                    }

                    // Feedback buttons
                    HStack(spacing: MacSpacing.xs) {
                        Button { onFeedback("positive") } label: {
                            Image(systemName: "hand.thumbsup")
                                .font(MacTypography.smallBody)
                                .foregroundStyle(MacColors.textFaint)
                        }
                        .buttonStyle(.plain)

                        Button { onFeedback("negative") } label: {
                            Image(systemName: "hand.thumbsdown")
                                .font(MacTypography.smallBody)
                                .foregroundStyle(MacColors.textFaint)
                        }
                        .buttonStyle(.plain)
                    }

                    // Timestamp
                    Text(formatTradeTime(trade.timestamp))
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)

                    Image(systemName: "chevron.right")
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.textFaint)
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                }
                .padding(MacSpacing.md)
            }
            .buttonStyle(.plain)

            // Decision Trail (expanded)
            if isExpanded {
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    MacColors.divider
                        .frame(height: 1)

                    Text("Decision Trail")
                        .font(MacTypography.captionMedium)
                        .foregroundStyle(MacColors.amberAccent)

                    if let trail = trade.decisionTrail, !trail.isEmpty {
                        ForEach(Array(trail.enumerated()), id: \.offset) { index, step in
                            trailStepView(step)
                        }
                    } else {
                        Text("No decision trail recorded")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
                .padding(.horizontal, MacSpacing.md)
                .padding(.bottom, MacSpacing.md)
            }
        }
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func confidenceGauge(score: Double) -> some View {
        ZStack {
            Circle()
                .stroke(MacColors.textFaint.opacity(0.2), lineWidth: 2.5)
                .frame(width: 28, height: 28)
            Circle()
                .trim(from: 0, to: score)
                .stroke(gaugeColor(score), style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                .frame(width: 28, height: 28)
                .rotationEffect(.degrees(-90))
            Text("\(Int(score * 100))")
                .font(.system(size: 8, weight: .bold, design: .monospaced))
                .foregroundStyle(MacColors.textPrimary)
        }
    }

    private func gaugeColor(_ score: Double) -> Color {
        if score >= 0.8 { return MacColors.healthGreen }
        if score >= 0.5 { return MacColors.healthAmber }
        return MacColors.healthRed
    }

    private func trailStepView(_ step: TrailStep) -> some View {
        let stepName = step.step ?? "unknown"
        let icon = trailStepIcon(stepName)
        return HStack(alignment: .top, spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 14)
            VStack(alignment: .leading, spacing: 1) {
                Text(stepName.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(MacColors.textSecondary)
            }
        }
    }

    private func trailStepIcon(_ step: String) -> String {
        switch step {
        case "risk_validation": return "shield"
        case "price_validation": return "cloud.sun"
        case "exchange_execution": return "arrow.left.arrow.right"
        default: return "circle"
        }
    }

    private func formatTradeTime(_ timestamp: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: timestamp) ?? ISO8601DateFormatter().date(from: timestamp) else {
            return timestamp.prefix(16).description
        }
        let display = DateFormatter()
        display.dateFormat = "HH:mm"
        return display.string(from: date)
    }
}
