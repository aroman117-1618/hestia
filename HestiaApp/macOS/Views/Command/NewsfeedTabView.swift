import SwiftUI
import HestiaShared

struct NewsfeedTabView: View {
    @StateObject private var viewModel = NewsfeedTabViewModel()

    private let cardBackground = Color(red: 17/255, green: 11/255, blue: 3/255)
    private let cardBorder = Color(red: 26/255, green: 20/255, blue: 8/255)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: MacSpacing.xl) {
                // Section 1: Trading
                tradingSection

                // Section 2 + 3: Orders & Investigations (side by side)
                HStack(alignment: .top, spacing: MacSpacing.md) {
                    ordersSection
                    investigationsSection
                }
            }
            .padding(MacSpacing.md)
        }
        .task {
            await viewModel.loadData()
        }
    }

    // MARK: - Trading Section

    private var tradingSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header row
            HStack {
                Text("TRADING")
                    .font(.system(size: 11))
                    .tracking(0.8)
                    .foregroundStyle(MacColors.textSecondary)

                Spacer()

                PLLookbackToggle(selection: $viewModel.lookbackPeriod)
            }

            TradingStatusView(
                summary: viewModel.tradingSummary,
                positions: viewModel.positions,
                bots: viewModel.bots
            )
        }
    }

    // MARK: - Orders Section

    private var ordersSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("ORDERS")
                .font(.system(size: 11))
                .tracking(0.8)
                .foregroundStyle(MacColors.textSecondary)

            VStack(alignment: .leading, spacing: 0) {
                if viewModel.orders.isEmpty {
                    emptyState(icon: "bolt.slash", message: "No orders scheduled")
                } else {
                    ForEach(viewModel.orders) { order in
                        orderRow(order)
                        if order.id != viewModel.orders.last?.id {
                            Divider()
                                .background(MacColors.divider)
                        }
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
    }

    private func orderRow(_ order: OrderResponse) -> some View {
        HStack(spacing: MacSpacing.sm) {
            // Status icon
            orderStatusIcon(order)

            Text(order.name)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()

            Text(orderDetail(order))
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
        }
        .padding(.vertical, MacSpacing.xs)
    }

    private func orderStatusIcon(_ order: OrderResponse) -> some View {
        Group {
            if let execution = order.lastExecution {
                switch execution.status {
                case .success:
                    Image(systemName: "checkmark")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(Color.green)
                case .running:
                    Image(systemName: "circle.fill")
                        .font(.system(size: 8))
                        .foregroundStyle(MacColors.amberAccent)
                case .scheduled:
                    Image(systemName: "arrowtriangle.right.fill")
                        .font(.system(size: 8))
                        .foregroundStyle(Color.green)
                case .failed:
                    Image(systemName: "xmark")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(Color.red)
                }
            } else {
                Image(systemName: "arrowtriangle.right.fill")
                    .font(.system(size: 8))
                    .foregroundStyle(Color.green)
            }
        }
        .frame(width: 14)
    }

    private func orderDetail(_ order: OrderResponse) -> String {
        if let execution = order.lastExecution {
            switch execution.status {
            case .running:
                return "Running..."
            case .success:
                let formatter = DateFormatter()
                formatter.dateFormat = "h:mm a"
                return "Completed \(formatter.string(from: execution.timestamp))"
            case .scheduled:
                return "Scheduled \(order.scheduledTime)"
            case .failed:
                return "Failed"
            }
        }
        return "Scheduled \(order.scheduledTime)"
    }

    // MARK: - Investigations Section

    private var investigationsSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("INVESTIGATION FINDINGS")
                .font(.system(size: 11))
                .tracking(0.8)
                .foregroundStyle(MacColors.textSecondary)

            VStack(alignment: .leading, spacing: 0) {
                if viewModel.investigations.isEmpty {
                    emptyState(icon: "magnifyingglass", message: "No recent investigations")
                } else {
                    ForEach(viewModel.investigations) { investigation in
                        investigationRow(investigation)
                        if investigation.id != viewModel.investigations.last?.id {
                            Divider()
                                .background(MacColors.divider)
                        }
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
    }

    private func investigationRow(_ investigation: Investigation) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(Color.purple)
                    .frame(width: 6, height: 6)

                Text(investigation.displayTitle)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                Spacer()

                Text(investigation.createdAt)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textSecondary)
            }

            if !investigation.analysis.isEmpty {
                Text(investigation.analysis)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(1)
                    .padding(.leading, 14)
            }
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
}
