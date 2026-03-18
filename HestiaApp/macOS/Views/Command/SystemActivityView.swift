import SwiftUI
import HestiaShared

// MARK: - System Activity Tab

struct SystemActivityView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                // Active Workflows / Orders
                CollapsibleSection(
                    title: "Active Workflows",
                    icon: "arrow.clockwise",
                    count: viewModel.orders.count
                ) {
                    ordersContent
                }

                // Memory Activity
                CollapsibleSection(
                    title: "Memory Activity",
                    icon: "brain",
                    count: viewModel.memoryChunkCount > 0 ? 1 : 0
                ) {
                    memoryContent
                }

                // System Alerts
                CollapsibleSection(
                    title: "System Alerts",
                    icon: "exclamationmark.triangle",
                    count: viewModel.unacknowledgedAlertCount,
                    countColor: viewModel.unacknowledgedAlertCount > 0 ? MacColors.healthRed : MacColors.healthGreen
                ) {
                    alertsContent
                }
            }
            .padding(.top, MacSpacing.lg)
        }
    }

    // MARK: - Orders

    @ViewBuilder
    private var ordersContent: some View {
        if viewModel.orders.isEmpty {
            sectionEmptyState(icon: "bolt.slash", message: "No active orders")
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(viewModel.orders.prefix(6)) { order in
                    orderRow(order)
                }
            }
        }
    }

    private func orderRow(_ order: OrderResponse) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: order.status == .active ? "play.circle.fill" : "pause.circle")
                .font(.system(size: 16))
                .foregroundStyle(order.status == .active ? MacColors.healthGreen : MacColors.textSecondary)

            VStack(alignment: .leading, spacing: 2) {
                Text(order.name)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                HStack(spacing: MacSpacing.sm) {
                    Text(order.frequency.type.rawValue.capitalized)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)

                    if let next = order.nextExecution {
                        Text("Next: \(next, style: .relative)")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            }

            Spacer()

            orderStatusBadge(order.status)
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func orderStatusBadge(_ status: APIOrderStatus) -> some View {
        let (text, color): (String, Color) = switch status {
        case .active: ("Active", MacColors.healthGreen)
        case .inactive: ("Inactive", MacColors.textSecondary)
        }

        return Text(text)
            .font(MacTypography.metadata)
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 3.5)
            .background(color.opacity(0.15))
            .clipShape(Capsule())
    }

    // MARK: - Memory Activity

    @ViewBuilder
    private var memoryContent: some View {
        if viewModel.memoryHealth == nil && viewModel.metaMonitorReport == nil {
            sectionEmptyState(icon: "brain", message: "No memory health data")
        } else {
            VStack(spacing: MacSpacing.md) {
                // Metrics row
                HStack(spacing: MacSpacing.md) {
                    memoryMetric(
                        icon: "square.stack.3d.up",
                        label: "Total Chunks",
                        value: "\(viewModel.memoryChunkCount)",
                        color: MacColors.textSecondary
                    )
                    memoryMetric(
                        icon: "doc.on.doc",
                        label: "Redundancy",
                        value: String(format: "%.1f%%", viewModel.memoryRedundancyPct),
                        color: viewModel.memoryRedundancyPct > 20 ? MacColors.healthRed : MacColors.healthGreen
                    )
                    memoryMetric(
                        icon: "face.smiling",
                        label: "Positive Ratio",
                        value: "\(viewModel.positiveRatioPercent)%",
                        color: viewModel.positiveRatioPercent > 70 ? MacColors.healthGreen : MacColors.healthAmber
                    )
                }

                // Last consolidation info
                if let health = viewModel.memoryHealth {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "clock")
                            .font(.system(size: 11))
                            .foregroundStyle(MacColors.textFaint)
                        Text("Last snapshot: \(health.timestamp)")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                            .lineLimit(1)
                    }
                }
            }
        }
    }

    private func memoryMetric(icon: String, label: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                    .foregroundStyle(color)
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
            Text(value)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(MacColors.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Alerts

    @ViewBuilder
    private var alertsContent: some View {
        let unacknowledged = viewModel.triggerAlerts.filter { !$0.acknowledged }
        if unacknowledged.isEmpty {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.healthGreen)
                Text("No active alerts — all systems nominal")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(MacSpacing.md)
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(unacknowledged, id: \.id) { alert in
                    alertRow(alert)
                }
            }
        }
    }

    private func alertRow(_ alert: TriggerAlert) -> some View {
        HStack(spacing: MacSpacing.md) {
            Circle()
                .fill(MacColors.healthRed)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(alert.triggerName)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Text(alert.message)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(2)
            }

            Spacer()

            Text(alert.timestamp)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)
                .lineLimit(1)
        }
        .padding(MacSpacing.md)
        .background(MacColors.healthRedBg)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .strokeBorder(MacColors.healthRedBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Empty State

    private func sectionEmptyState(icon: String, message: String) -> some View {
        VStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundStyle(MacColors.textSecondary.opacity(0.5))
            Text(message)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, MacSpacing.xl)
    }
}

// MARK: - Collapsible Section (reusable)

struct CollapsibleSection<Content: View>: View {
    let title: String
    let icon: String
    var count: Int = 0
    var countColor: Color = MacColors.amberAccent
    @ViewBuilder let content: () -> Content

    @State private var isExpanded: Bool = true

    var body: some View {
        VStack(spacing: 0) {
            // Header
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: icon)
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.amberAccent)
                        .frame(width: 20)

                    Text(title)
                        .font(MacTypography.sectionTitle)
                        .foregroundStyle(MacColors.textPrimary)

                    if count > 0 {
                        Text("\(count)")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(countColor)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(countColor.opacity(0.15))
                            .clipShape(Capsule())
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(MacColors.textFaint)
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                }
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)
            }
            .buttonStyle(.hestia)

            // Content
            if isExpanded {
                VStack(spacing: 0) {
                    MacColors.divider
                        .frame(height: 1)
                        .padding(.horizontal, MacSpacing.lg)

                    content()
                        .padding(.horizontal, MacSpacing.lg)
                        .padding(.vertical, MacSpacing.md)
                }
            }
        }
        .background(MacColors.panelBackground)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }
}
