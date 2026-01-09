import SwiftUI

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
                    .foregroundColor(.white)

                Spacer()

                Text("Last 48 hours")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.4))
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
                .foregroundColor(.white.opacity(0.3))

            Text("No recent alerts")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.5))

            Text("Order executions from the last 48 hours will appear here")
                .font(.caption)
                .foregroundColor(.white.opacity(0.3))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.white.opacity(0.05))
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
                            .foregroundColor(.white)

                        HStack(spacing: Spacing.xs) {
                            Text(execution.status.displayName)
                                .font(.caption)
                                .foregroundColor(statusColor)

                            Text("\u{2022}")
                                .foregroundColor(.white.opacity(0.3))

                            Text(execution.formattedTimestamp)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.5))
                        }
                    }

                    Spacer()

                    // Expand indicator (only if there's content to show)
                    if execution.hestiaRead != nil || execution.fullResponse != nil {
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))
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
                                .foregroundColor(.white.opacity(0.6))

                            Text(hestiaRead)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }

                    if let fullResponse = execution.fullResponse {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("Full Response")
                                .font(.caption.weight(.semibold))
                                .foregroundColor(.white.opacity(0.6))

                            Text(fullResponse)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                                .lineLimit(10)
                        }
                    }
                }
                .padding(.horizontal, Spacing.md)
                .padding(.bottom, Spacing.md)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private var statusColor: Color {
        switch execution.status {
        case .success: return .healthyGreen
        case .failed: return .errorRed
        case .running: return .warningYellow
        case .scheduled: return .white.opacity(0.5)
        }
    }
}

// MARK: - Preview

struct AlertsWidget_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

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
