import SwiftUI
import HestiaShared

// MARK: - Trading Monitor (Sprint 26 placeholder with full component structure)

struct TradingMonitorView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                // Portfolio Snapshot
                portfolioSnapshotCard

                // Active Positions
                CollapsibleSection(
                    title: "Active Positions",
                    icon: "arrow.triangle.swap"
                ) {
                    emptyListState(
                        icon: "chart.bar.xaxis",
                        message: "No active positions",
                        detail: "Positions will appear when trading begins"
                    )
                }

                // Recent Trades
                CollapsibleSection(
                    title: "Recent Trades",
                    icon: "list.bullet.rectangle"
                ) {
                    // Mock trade rows with expandable decision trail
                    VStack(spacing: MacSpacing.sm) {
                        tradeRow(
                            pair: "BTC/USD",
                            side: .buy,
                            amount: "$127.50",
                            price: "$67,842.30",
                            hestiaScore: 0.82,
                            time: "Mock data"
                        )
                        tradeRow(
                            pair: "ETH/USD",
                            side: .sell,
                            amount: "$45.00",
                            price: "$3,521.15",
                            hestiaScore: 0.71,
                            time: "Mock data"
                        )
                    }
                }

                // Watchlist
                CollapsibleSection(
                    title: "Watchlist",
                    icon: "eye"
                ) {
                    emptyListState(
                        icon: "binoculars",
                        message: "No assets being watched",
                        detail: "Add pairs to your watchlist to monitor"
                    )
                }

                // Risk Status
                riskStatusCard

                // Kill Switch
                killSwitchButton
            }
            .padding(.top, MacSpacing.lg)
        }
    }

    // MARK: - Portfolio Snapshot

    private var portfolioSnapshotCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                Image(systemName: "chart.pie")
                    .font(.system(size: 14))
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
                    Text("$0.00")
                        .font(.system(size: 24, weight: .bold, design: .monospaced))
                        .foregroundStyle(MacColors.textPrimary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: MacSpacing.xs) {
                    Text("24h P&L")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    Text("$0.00")
                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                        .foregroundStyle(MacColors.textSecondary)
                }

                VStack(alignment: .trailing, spacing: MacSpacing.xs) {
                    Text("Open Positions")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    Text("0")
                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            // Status banner
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12))
                Text("Trading module loading — connect in Sprint 26")
                    .font(MacTypography.caption)
            }
            .foregroundStyle(MacColors.amberAccent)
            .padding(MacSpacing.sm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(MacColors.amberAccent.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .padding(MacSpacing.xl)
        .background(MacColors.panelBackground)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Trade Row (with expandable Decision Trail)

    private func tradeRow(pair: String, side: TradeSide, amount: String, price: String, hestiaScore: Double, time: String) -> some View {
        TradeRowView(pair: pair, side: side, amount: amount, price: price, hestiaScore: hestiaScore, time: time)
    }

    // MARK: - Risk Status

    private var riskStatusCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.amberAccent)
                Text("Risk Status")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()

                // Traffic light
                HStack(spacing: MacSpacing.xs) {
                    Circle()
                        .fill(MacColors.textSecondary.opacity(0.3))
                        .frame(width: 10, height: 10)
                    Text("Not connected")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            HStack(spacing: MacSpacing.md) {
                riskMetric(label: "Daily Drawdown", value: "—", limit: "3%")
                riskMetric(label: "Position Size", value: "—", limit: "2%")
                riskMetric(label: "Consec. Losses", value: "—", limit: "5")
            }
        }
        .padding(MacSpacing.xl)
        .background(MacColors.panelBackground)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    private func riskMetric(label: String, value: String, limit: String) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text(label)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textSecondary)
            HStack(alignment: .firstTextBaseline, spacing: MacSpacing.xs) {
                Text(value)
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundStyle(MacColors.textPrimary)
                Text("/ \(limit)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(MacColors.textFaint)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Kill Switch

    private var killSwitchButton: some View {
        Button {} label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "power")
                    .font(.system(size: 14, weight: .bold))
                Text("Emergency Kill Switch")
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundStyle(MacColors.healthRed.opacity(0.5))
            .frame(maxWidth: .infinity)
            .padding(.vertical, MacSpacing.md)
            .background(MacColors.healthRed.opacity(0.06))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(MacColors.healthRed.opacity(0.15), lineWidth: 1)
            }
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
        .buttonStyle(.plain)
        .disabled(true)
        .accessibilityLabel("Emergency kill switch — disabled until trading module connects")
    }

    // MARK: - Empty List State

    private func emptyListState(icon: String, message: String, detail: String) -> some View {
        VStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 20))
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
}

// MARK: - Trade Side

enum TradeSide {
    case buy, sell

    var label: String {
        switch self {
        case .buy: return "BUY"
        case .sell: return "SELL"
        }
    }

    var color: Color {
        switch self {
        case .buy: return MacColors.healthGreen
        case .sell: return MacColors.healthRed
        }
    }
}

// MARK: - Trade Row View (expandable with Decision Trail + satisfaction slots)

struct TradeRowView: View {
    let pair: String
    let side: TradeSide
    let amount: String
    let price: String
    let hestiaScore: Double
    let time: String

    @State private var isExpanded = false

    var body: some View {
        VStack(spacing: 0) {
            // Main row
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: MacSpacing.md) {
                    // Side badge
                    Text(side.label)
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(side.color)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(side.color.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 4))

                    // Pair + price
                    VStack(alignment: .leading, spacing: 1) {
                        Text(pair)
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(MacColors.textPrimary)
                        Text("\(amount) @ \(price)")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    Spacer()

                    // Hestia satisfaction score gauge slot
                    satisfactionGauge(score: hestiaScore)

                    // User feedback slot (thumbs)
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "hand.thumbsup")
                            .font(.system(size: 12))
                            .foregroundStyle(MacColors.textFaint)
                        Image(systemName: "hand.thumbsdown")
                            .font(.system(size: 12))
                            .foregroundStyle(MacColors.textFaint)
                    }

                    // Time
                    Text(time)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)

                    // Expand chevron
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .medium))
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
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(MacColors.amberAccent)

                    trailStep(icon: "antenna.radiowaves.left.and.right", label: "Signal", value: "Grid level hit — price crossed geometric boundary")
                    trailStep(icon: "gearshape", label: "Strategy", value: "Geometric grid — 2.5% spacing, 15 levels")
                    trailStep(icon: "shield", label: "Risk Check", value: "Passed — position 0.8% of portfolio (limit 2%)")
                    trailStep(icon: "cloud.sun", label: "Market", value: "Neutral regime — volatility within 1σ")
                    trailStep(icon: "brain", label: "Hestia", value: "Confidence 82% — no override signals detected")
                }
                .padding(.horizontal, MacSpacing.md)
                .padding(.bottom, MacSpacing.md)
            }
        }
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Satisfaction Gauge

    private func satisfactionGauge(score: Double) -> some View {
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

    // MARK: - Trail Step

    private func trailStep(icon: String, label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 14)
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(MacColors.textSecondary)
                Text(value)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textPrimary)
            }
        }
    }
}
