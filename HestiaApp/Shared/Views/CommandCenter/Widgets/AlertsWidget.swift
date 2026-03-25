import SwiftUI
import HestiaShared

/// Widget showing recent order execution alerts (last 48 hours)
struct AlertsWidget: View {
    let executions: [OrderExecution]
    let orders: [Order]

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Header
            HStack {
                Text("Alerts")
                    .font(.headline)
                    .foregroundColor(.textPrimary)

                Spacer()

                Text("Last 48 hours")
                    .font(.caption)
                    .foregroundColor(.textTertiary)
            }
            .padding(.horizontal, Spacing.lg)

            if executions.isEmpty {
                emptyState
            } else {
                ForEach(executions) { execution in
                    AlertRow(
                        execution: execution,
                        orderName: orderName(for: execution.orderId)
                    )
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "bell.slash")
                .font(.system(size: 32))
                .foregroundColor(.textTertiary)

            Text("No recent alerts")
                .font(.subheadline)
                .foregroundColor(.textSecondary)

            Text("Order executions from the last 48 hours will appear here")
                .font(.caption)
                .foregroundColor(.textTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private func orderName(for orderId: UUID) -> String {
        orders.first { $0.id == orderId }?.name ?? "Unknown Order"
    }
}

// MARK: - Alert Row

struct AlertRow: View {
    let execution: OrderExecution
    let orderName: String

    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Main row
            Button {
                withAnimation(.hestiaStandard) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: Spacing.md) {
                    // Status icon
                    Image(systemName: execution.status.iconName)
                        .font(.system(size: 20))
                        .foregroundColor(statusColor)

                    // Info
                    VStack(alignment: .leading, spacing: 2) {
                        Text(orderName)
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(.textPrimary)

                        HStack(spacing: Spacing.xs) {
                            Text(execution.status.displayName)
                                .font(.caption)
                                .foregroundColor(statusColor)

                            Text("\u{2022}")
                                .foregroundColor(.textTertiary)

                            Text(execution.formattedTimestamp)
                                .font(.caption)
                                .foregroundColor(.textSecondary)
                        }
                    }

                    Spacer()

                    // Expand indicator (only if there's content to show)
                    if execution.hestiaRead != nil || execution.fullResponse != nil {
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                            .foregroundColor(.textTertiary)
                    }
                }
                .padding(Spacing.md)
            }
            .buttonStyle(PlainButtonStyle())

            // Expanded content
            if isExpanded {
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    if let hestiaRead = execution.hestiaRead {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("Analysis")
                                .font(.caption.weight(.semibold))
                                .foregroundColor(.textSecondary)

                            Text(hestiaRead)
                                .font(.caption)
                                .foregroundColor(.textPrimary.opacity(0.8))
                        }
                    }

                    if let fullResponse = execution.fullResponse {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("Full Response")
                                .font(.caption.weight(.semibold))
                                .foregroundColor(.textSecondary)

                            Text(fullResponse)
                                .font(.caption)
                                .foregroundColor(.textSecondary)
                                .lineLimit(10)
                        }
                    }
                }
                .padding(.horizontal, Spacing.md)
                .padding(.bottom, Spacing.md)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private var statusColor: Color {
        switch execution.status {
        case .success: return .healthyGreen
        case .failed: return .errorRed
        case .running: return .warningYellow
        case .scheduled: return .textSecondary
        }
    }
}

// MARK: - Preview

struct AlertsWidget_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.bgBase.ignoresSafeArea()

            ScrollView {
                AlertsWidget(
                    executions: [
                        OrderExecution(
                            id: UUID(),
                            orderId: UUID(),
                            timestamp: Date().addingTimeInterval(-3600),
                            status: .success,
                            hestiaRead: nil,
                            fullResponse: "Morning brief completed successfully"
                        ),
                        OrderExecution(
                            id: UUID(),
                            orderId: UUID(),
                            timestamp: Date().addingTimeInterval(-7200),
                            status: .failed,
                            hestiaRead: "Unable to connect to Fidelity API. The service may be temporarily unavailable.",
                            fullResponse: nil
                        )
                    ],
                    orders: Order.mockOrders
                )
            }
        }
    }
}
