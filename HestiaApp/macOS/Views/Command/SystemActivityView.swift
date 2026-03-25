import SwiftUI
import HestiaShared

// MARK: - System Activity Tab

struct SystemActivityView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    enum OrdersTab: String, CaseIterable {
        case upcoming = "Upcoming"
        case past = "Past"
    }

    @State private var ordersTab: OrdersTab = .upcoming
    @State private var showNewOrderSheet = false

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                // Workflows
                CollapsibleSection(
                    title: "Orders",
                    icon: "arrow.triangle.branch",
                    count: viewModel.activeWorkflowCount
                ) {
                    workflowsContent
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
        .sheet(isPresented: $showNewOrderSheet) {
            NewOrderSheet()
        }
    }

    // MARK: - Workflows

    @ViewBuilder
    private var workflowsContent: some View {
        if viewModel.activeWorkflows.isEmpty {
            sectionEmptyState(icon: "arrow.triangle.branch", message: "No orders created")
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(viewModel.activeWorkflows, id: \.id) { workflow in
                    workflowCard(workflow)
                }
            }
        }
    }

    private func workflowCard(_ workflow: WorkflowSummary) -> some View {
        let isActive = workflow.status == "active"
        let statusColor = isActive ? MacColors.healthGreen : MacColors.healthAmber
        let statusLabel = workflow.status.capitalized

        return VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text(workflow.name)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Spacer()
                Text(statusLabel)
                    .font(MacTypography.metadata)
                    .foregroundStyle(statusColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(statusColor.opacity(0.15))
                    .clipShape(Capsule())
            }

            HStack(spacing: MacSpacing.md) {
                // Trigger type
                HStack(spacing: 4) {
                    Image(systemName: workflow.triggerType == "schedule" ? "clock" : "hand.tap")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    Text(workflow.triggerType.capitalized)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }

                Spacer()

                // Run count
                if workflow.runCount > 0 {
                    HStack(spacing: 4) {
                        Text("\(workflow.runCount) runs")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                        let rate = workflow.successRate
                        Text(String(format: "%.0f%%", rate * 100))
                            .font(MacTypography.caption)
                            .foregroundStyle(rate > 0.8 ? MacColors.healthGreen : MacColors.healthAmber)
                    }
                }
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(statusColor)
                .frame(width: 3)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Orders (Legacy)

    @ViewBuilder
    private var ordersContent: some View {
        VStack(spacing: MacSpacing.md) {
            // Upcoming/Past toggle
            Picker("", selection: $ordersTab) {
                ForEach(OrdersTab.allCases, id: \.self) { tab in
                    Text(tab.rawValue).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 200)

            // Content based on tab
            switch ordersTab {
            case .upcoming:
                upcomingOrdersContent
            case .past:
                pastOrdersContent
            }
        }
    }

    // MARK: - Upcoming Orders

    @ViewBuilder
    private var upcomingOrdersContent: some View {
        if viewModel.orders.isEmpty {
            sectionEmptyState(icon: "bolt.slash", message: "No active orders")
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(viewModel.orders) { order in
                    upcomingOrderCard(order)
                }

                // Add Order button
                Button {
                    showNewOrderSheet = true
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "plus")
                            .font(MacTypography.label)
                        Text("New Order")
                            .font(MacTypography.label)
                    }
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, MacSpacing.sm)
                    .overlay(
                        RoundedRectangle(cornerRadius: MacCornerRadius.search)
                            .strokeBorder(MacColors.textSecondary.opacity(0.3), style: StrokeStyle(lineWidth: 1, dash: [5]))
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func upcomingOrderCard(_ order: OrderResponse) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text(order.name)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Spacer()
                // Status badge
                Text(order.status == .active ? "Active" : "Scheduled")
                    .font(MacTypography.metadata)
                    .foregroundStyle(order.status == .active ? MacColors.healthGreen : MacColors.healthAmber)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background((order.status == .active ? MacColors.healthGreen : MacColors.healthAmber).opacity(0.15))
                    .clipShape(Capsule())
            }

            HStack {
                // Recurrence
                HStack(spacing: 4) {
                    Text("\u{1F501}")
                        .font(MacTypography.caption)
                    Text(order.frequency.type.rawValue.capitalized)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }

                Spacer()

                // Next execution
                if let next = order.nextExecution {
                    Text("Next: \(next, style: .relative)")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                }
            }

            // Last run
            if let lastExec = order.lastExecution {
                HStack {
                    Spacer()
                    Text("Last: \(lastExec.timestamp, style: .relative) ago")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    let statusIcon = lastExec.status == .success ? "\u{2713}" : "\u{2717}"
                    let statusColor = lastExec.status == .success ? MacColors.healthGreen : MacColors.healthRed
                    Text(statusIcon)
                        .font(MacTypography.caption)
                        .foregroundStyle(statusColor)
                }
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(order.status == .active ? MacColors.healthGreen : MacColors.healthAmber)
                .frame(width: 3)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Past Orders

    @ViewBuilder
    private var pastOrdersContent: some View {
        let pastExecutions = viewModel.orders.filter { $0.lastExecution != nil }
        if pastExecutions.isEmpty {
            sectionEmptyState(icon: "clock", message: "No past executions")
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(pastExecutions) { order in
                    pastOrderCard(order)
                }
            }
        }
    }

    private func pastOrderCard(_ order: OrderResponse) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(order.name)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                if let lastExec = order.lastExecution {
                    Text(lastExec.timestamp, style: .relative)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
            Spacer()
            // Success/failure based on last execution status
            if let lastExec = order.lastExecution {
                let isSuccess = lastExec.status == .success
                Text(isSuccess ? "\u{2713} Success" : "\u{2717} Failed")
                    .font(MacTypography.caption)
                    .foregroundStyle(isSuccess ? MacColors.healthGreen : MacColors.healthRed)
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .opacity(0.8)
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
                            .font(MacTypography.caption)
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
                    .font(MacTypography.caption)
                    .foregroundStyle(color)
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
            Text(value)
                .font(MacTypography.sectionTitle)
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
                    .font(MacTypography.sectionTitle)
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
                .font(MacTypography.pageTitle)
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
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.amberAccent)
                        .frame(width: 20)

                    Text(title)
                        .font(MacTypography.sectionTitle)
                        .foregroundStyle(MacColors.textPrimary)

                    if count > 0 {
                        Text("\(count)")
                            .font(MacTypography.captionMedium)
                            .foregroundStyle(countColor)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(countColor.opacity(0.15))
                            .clipShape(Capsule())
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(MacTypography.smallMedium)
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
        .hestiaPanel()
    }
}
