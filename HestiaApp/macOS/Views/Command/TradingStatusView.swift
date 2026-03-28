import SwiftUI
import HestiaShared

struct TradingStatusView: View {
    let summary: TradingSummary?
    let positions: [TradingPositionEntry]
    let bots: [TradingBotResponse]

    private let cardBackground = Color(red: 17/255, green: 11/255, blue: 3/255)
    private let cardBorder = Color(red: 26/255, green: 20/255, blue: 8/255)

    var body: some View {
        HStack(alignment: .top, spacing: MacSpacing.md) {
            statusCard
            positionsTable
        }
    }

    // MARK: - Status Card (Left)

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Status indicator
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(activeBotCount > 0 ? Color.green : MacColors.textPlaceholder)
                    .frame(width: 8, height: 8)
                Text(activeBotCount > 0 ? "All Systems Live" : "No bots active")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
            }

            // 2x2 Stats Grid
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: MacSpacing.md) {
                statCell(label: "P&L", value: pnlString, color: pnlColor)
                statCell(label: "Fills", value: "\(summary?.totalTrades ?? 0)", color: MacColors.textPrimary)
                statCell(label: "Win Rate", value: winRateString, color: MacColors.textPrimary)
                statCell(label: "Drawdown", value: "--", color: MacColors.textPrimary)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(cardBackground)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(cardBorder, lineWidth: 1)
        )
    }

    private func statCell(label: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
            Text(value)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(color)
        }
    }

    // MARK: - Positions Table (Right)

    private var positionsTable: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text("Pair")
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text("Side")
                    .frame(width: 50, alignment: .leading)
                Text("Entry")
                    .frame(width: 70, alignment: .trailing)
                Text("Current")
                    .frame(width: 70, alignment: .trailing)
                Text("P&L")
                    .frame(width: 60, alignment: .trailing)
            }
            .font(.system(size: 10))
            .foregroundStyle(MacColors.textSecondary)
            .padding(.bottom, MacSpacing.sm)

            Divider()
                .background(MacColors.divider)

            if positions.isEmpty {
                emptyState(icon: "chart.bar", message: "No open positions")
            } else {
                ForEach(positions) { position in
                    positionRow(position)
                    Divider()
                        .background(MacColors.divider)
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(cardBackground)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(cardBorder, lineWidth: 1)
        )
    }

    private func positionRow(_ position: TradingPositionEntry) -> some View {
        HStack {
            Text(position.currency)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(position.quantity > 0 ? "LONG" : "SHORT")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(position.quantity > 0 ? Color.green : Color.red)
                .frame(width: 50, alignment: .leading)
            Text(formatPrice(position.price))
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .frame(width: 70, alignment: .trailing)
            Text(formatPrice(position.price))
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .frame(width: 70, alignment: .trailing)
            let pnl = position.value - (position.price * position.quantity)
            Text(formatPnl(pnl))
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(pnl >= 0 ? Color.green : Color.red)
                .frame(width: 60, alignment: .trailing)
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Empty State

    private func emptyState(icon: String, message: String) -> some View {
        VStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundStyle(MacColors.textPlaceholder)
            Text(message)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPlaceholder)
        }
        .frame(maxWidth: .infinity, minHeight: 80)
    }

    // MARK: - Computed Helpers

    private var activeBotCount: Int {
        bots.filter { $0.status == "running" }.count
    }

    private var pnlString: String {
        guard let s = summary else { return "--" }
        let sign = s.totalPnl >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", s.totalPnl))"
    }

    private var pnlColor: Color {
        guard let s = summary else { return MacColors.textPrimary }
        return s.totalPnl >= 0 ? Color.green : Color.red
    }

    private var winRateString: String {
        guard let s = summary else { return "--" }
        return "\(String(format: "%.0f", s.winRate * 100))%"
    }

    private func formatPrice(_ price: Double) -> String {
        if price >= 1000 {
            return String(format: "$%.0f", price)
        } else if price >= 1 {
            return String(format: "$%.2f", price)
        } else {
            return String(format: "$%.4f", price)
        }
    }

    private func formatPnl(_ value: Double) -> String {
        let sign = value >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", value))"
    }
}
