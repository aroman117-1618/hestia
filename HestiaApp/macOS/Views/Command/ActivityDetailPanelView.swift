import SwiftUI
import HestiaShared

// MARK: - Activity Detail Panel

struct ActivityDetailPanelView: View {
    let item: NewsfeedItem
    let runDetail: WorkflowRunDetail?
    let isLoadingDetail: Bool
    let onClose: () -> Void
    let onSendToChat: (String) -> Void

    var body: some View {
        VStack(spacing: 0) {
            detailHeader
            Divider()
                .overlay(MacColors.divider)

            ScrollView {
                detailBody
                    .padding(MacSpacing.lg)
            }

            Divider()
                .overlay(MacColors.divider)
            actionBar
        }
        .frame(width: 420)
        .background(MacColors.sidebarBackground)
        .overlay(alignment: .leading) {
            MacColors.sidebarBorder.frame(width: 1)
        }
    }

    // MARK: - Header

    private var detailHeader: some View {
        HStack(alignment: .top, spacing: MacSpacing.sm) {
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text(item.title)
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(2)

                Text(item.relativeTime)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
            }

            Spacer()

            Button {
                onClose()
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 24, height: 24)
                    .background(MacColors.panelBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
        }
        .padding(MacSpacing.lg)
    }

    // MARK: - Body (type switch)

    @ViewBuilder
    private var detailBody: some View {
        if item.itemType == "order_execution" {
            orderExecutionContent
        } else if item.source == "trading" || item.source == "sentinel" {
            alertContent
        } else if item.source.contains("learning") || item.itemType.contains("suggestion") {
            selfDevContent
        } else {
            systemContent
        }
    }

    // MARK: - Order Execution

    private var orderExecutionContent: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            orderMetaRow

            sectionHeader("Execution Timeline")

            if isLoadingDetail && runDetail == nil {
                HStack {
                    Spacer()
                    ProgressView()
                        .controlSize(.small)
                    Spacer()
                }
                .padding(.vertical, MacSpacing.xl)
            } else if let detail = runDetail {
                executionTimeline(detail)
            } else {
                bodyText(item.body)
            }
        }
    }

    private var orderMetaRow: some View {
        HStack(spacing: MacSpacing.lg) {
            metaItem(label: "Status", value: runDetail?.status.capitalized ?? "Completed", color: statusColorForRun)
            metaItem(label: "Started", value: formattedStartTime)
            if let dur = runDetail?.durationMs {
                metaItem(label: "Duration", value: formatDuration(dur))
            }
            if let detail = runDetail {
                metaItem(label: "Steps", value: "\(detail.nodeExecutions.count)")
            }
        }
    }

    private var statusColorForRun: Color {
        guard let status = runDetail?.status else { return MacColors.healthGreen }
        switch status {
        case "success": return MacColors.healthGreen
        case "failed": return MacColors.healthRed
        case "running": return MacColors.statusInfo
        default: return MacColors.textSecondary
        }
    }

    private var formattedStartTime: String {
        guard let detail = runDetail, let date = ISO8601DateFormatter().date(from: detail.startedAt) else {
            return item.relativeTime
        }
        let fmt = DateFormatter()
        fmt.dateFormat = "HH:mm:ss"
        return fmt.string(from: date)
    }

    private func executionTimeline(_ detail: WorkflowRunDetail) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(detail.nodeExecutions.enumerated()), id: \.element.id) { index, execution in
                let isLast = index == detail.nodeExecutions.count - 1
                executionStep(execution, isLast: isLast)
            }
        }
    }

    private func executionStep(_ execution: NodeExecutionResponse, isLast: Bool) -> some View {
        HStack(alignment: .top, spacing: MacSpacing.sm) {
            // Rail
            VStack(spacing: 0) {
                Circle()
                    .fill(colorForExecutionStatus(execution.status))
                    .frame(width: 10, height: 10)

                if !isLast {
                    Rectangle()
                        .fill(MacColors.cardBorderStrong)
                        .frame(width: 1.5)
                        .frame(minHeight: 40)
                }
            }
            .frame(width: 24)

            // Body
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                HStack {
                    Text(execution.nodeId)
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.textPrimary)

                    typeBadge(execution.status.uppercased())

                    Spacer()

                    if let dur = execution.durationText {
                        Text(dur)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }

                if let error = execution.errorMessage, !error.isEmpty {
                    logBlock(error)
                }

                if let response = execution.responseText {
                    Text(response)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                        .textSelection(.enabled)
                        .padding(MacSpacing.md)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(MacColors.chatInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
            }
            .padding(.bottom, isLast ? 0 : MacSpacing.md)
        }
    }

    // MARK: - Alert Content

    private var alertContent: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            alertMetaRow

            if let description = item.body, !description.isEmpty {
                sectionHeader("Description")
                bodyText(description)
            }

            if let logs = extractLogs() {
                sectionHeader("Log")
                logBlock(logs)
            }
        }
    }

    private var alertMetaRow: some View {
        HStack(spacing: MacSpacing.lg) {
            if let severity = metadataString("severity") {
                VStack(alignment: .leading, spacing: 2) {
                    Text("SEVERITY")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                    severityBadge(severity)
                }
            }
            metaItem(label: "Source", value: item.source.capitalized)
            metaItem(label: "Time", value: item.relativeTime)
            metaItem(label: "Status", value: item.isRead ? "Read" : "Unread")
        }
    }

    // MARK: - Self-Dev / Idea Content

    private var selfDevContent: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            selfDevMetaRow

            if let description = item.body, !description.isEmpty {
                sectionHeader("Description")
                bodyText(description)
            }

            if let impact = metadataString("impact") {
                sectionHeader("Impact")
                impactCard(impact)
            }
        }
    }

    private var selfDevMetaRow: some View {
        HStack(spacing: MacSpacing.lg) {
            VStack(alignment: .leading, spacing: 2) {
                Text("CATEGORY")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                categoryBadge("Self-Development")
            }
            if let confidence = metadataString("confidence") {
                metaItem(label: "Confidence", value: confidence)
            }
            if let impact = metadataString("impact_level") {
                metaItem(label: "Impact", value: impact.capitalized)
            }
        }
    }

    // MARK: - System / Default Content

    private var systemContent: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            HStack(spacing: MacSpacing.lg) {
                metaItem(label: "Type", value: item.itemType.replacingOccurrences(of: "_", with: " ").capitalized)
                metaItem(label: "Time", value: item.relativeTime)
            }

            if let description = item.body, !description.isEmpty {
                sectionHeader("Description")
                bodyText(description)
            }

            if let logs = extractLogs() {
                sectionHeader("Log")
                logBlock(logs)
            }
        }
    }

    // MARK: - Action Bar

    private var actionBar: some View {
        VStack(spacing: MacSpacing.sm) {
            // Type-specific actions
            if item.itemType == "order_execution" {
                HStack(spacing: MacSpacing.sm) {
                    actionButton("View Canvas", style: .standard) {}
                    actionButton("Re-run", style: .standard) {}
                }
            } else if item.source == "trading" || item.source == "sentinel" {
                HStack(spacing: MacSpacing.sm) {
                    actionButton("Snooze", style: .standard) {}
                    actionButton("Investigate", style: .standard) {}
                    actionButton("Dismiss", style: .standard) {}
                }
            } else if item.source.contains("learning") || item.itemType.contains("suggestion") {
                HStack(spacing: MacSpacing.sm) {
                    actionButton("Dismiss", style: .danger) {}
                    actionButton("Preview", style: .standard) {}
                    actionButton("Accept & Run", style: .primary) {}
                }
            } else {
                HStack(spacing: MacSpacing.sm) {
                    actionButton("Dismiss", style: .primary) {}
                }
            }

            // Send to Chat — always present
            actionButton("Send to Chat", style: .primary) {
                let context = "Context from Activity: \(item.title)\n\(item.body ?? "")"
                onSendToChat(context)
            }
        }
        .padding(MacSpacing.lg)
    }

    // MARK: - Reusable Components

    private func sectionHeader(_ title: String) -> some View {
        Text(title.uppercased())
            .font(MacTypography.sectionLabel)
            .tracking(0.8)
            .foregroundStyle(MacColors.textFaint)
    }

    private func metaItem(label: String, value: String, color: Color = MacColors.textPrimary) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)
            Text(value)
                .font(MacTypography.label)
                .foregroundStyle(color)
        }
    }

    @ViewBuilder
    private func bodyText(_ text: String?) -> some View {
        if let text, !text.isEmpty {
            Text(text)
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func logBlock(_ text: String) -> some View {
        Text(text)
            .font(MacTypography.code)
            .foregroundStyle(MacColors.textSecondary)
            .padding(MacSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(MacColors.chatInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            .overlay(alignment: .leading) {
                MacColors.cardBorderStrong.frame(width: 2)
                    .clipShape(RoundedRectangle(cornerRadius: 1))
            }
    }

    private func typeBadge(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 9, weight: .semibold))
            .textCase(.uppercase)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(MacColors.panelBackground)
            .foregroundStyle(MacColors.textSecondary)
            .clipShape(RoundedRectangle(cornerRadius: 4))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(MacColors.cardBorder))
    }

    private func severityBadge(_ severity: String) -> some View {
        let color = severityColor(severity)
        return Text(severity.uppercased())
            .font(.system(size: 11, weight: .semibold))
            .textCase(.uppercase)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .background(color.opacity(0.12))
            .foregroundStyle(color)
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private func categoryBadge(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .semibold))
            .textCase(.uppercase)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .background(MacColors.sleepPurple.opacity(0.12))
            .foregroundStyle(MacColors.sleepPurple)
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private func impactCard(_ impact: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "chart.bar.fill")
                .font(.system(size: 14))
                .foregroundStyle(MacColors.amberAccent)
            Text(impact)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textPrimary)
        }
        .padding(MacSpacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .overlay(RoundedRectangle(cornerRadius: MacCornerRadius.search).stroke(MacColors.cardBorder))
    }

    // MARK: - Action Button

    private enum ButtonStyle {
        case standard
        case primary
        case danger
    }

    private func actionButton(_ title: String, style: ButtonStyle, action: @escaping () -> Void) -> some View {
        Button {
            action()
        } label: {
            Text(title)
                .font(MacTypography.labelMedium)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(backgroundForStyle(style))
        .foregroundStyle(foregroundForStyle(style))
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .stroke(borderForStyle(style))
        )
    }

    private func backgroundForStyle(_ style: ButtonStyle) -> Color {
        switch style {
        case .standard: return MacColors.panelBackground
        case .primary: return MacColors.amberAccent
        case .danger: return MacColors.panelBackground
        }
    }

    private func foregroundForStyle(_ style: ButtonStyle) -> Color {
        switch style {
        case .standard: return MacColors.textPrimary
        case .primary: return MacColors.buttonTextDark
        case .danger: return MacColors.healthRed
        }
    }

    private func borderForStyle(_ style: ButtonStyle) -> Color {
        switch style {
        case .standard: return MacColors.cardBorder
        case .primary: return Color.clear
        case .danger: return MacColors.healthRed.opacity(0.3)
        }
    }

    // MARK: - Helpers

    private func colorForExecutionStatus(_ status: String) -> Color {
        switch status {
        case "success": return MacColors.healthGreen
        case "failed": return MacColors.healthRed
        case "running": return MacColors.statusInfo
        default: return MacColors.textInactive
        }
    }

    private func severityColor(_ severity: String) -> Color {
        switch severity.lowercased() {
        case "high", "critical": return MacColors.healthRed
        case "medium": return MacColors.statusWarning
        case "low": return MacColors.statusInfo
        default: return MacColors.textSecondary
        }
    }

    private func formatDuration(_ ms: Double) -> String {
        if ms < 1000 { return "\(Int(ms))ms" }
        if ms < 60_000 { return String(format: "%.1fs", ms / 1000) }
        return String(format: "%.1fm", ms / 60_000)
    }

    private func metadataString(_ key: String) -> String? {
        guard let meta = item.metadata, let value = meta[key] else { return nil }
        switch value {
        case .string(let s): return s
        case .int(let i): return "\(i)"
        case .double(let d): return String(format: "%.1f", d)
        case .bool(let b): return b ? "Yes" : "No"
        default: return nil
        }
    }

    private func extractLogs() -> String? {
        guard let meta = item.metadata else { return nil }
        if let logVal = meta["logs"] {
            switch logVal {
            case .string(let s): return s
            case .array(let arr):
                let lines = arr.compactMap { entry -> String? in
                    if case .string(let s) = entry { return s }
                    return nil
                }
                return lines.isEmpty ? nil : lines.joined(separator: "\n")
            default: return nil
            }
        }
        if let logVal = meta["log"] {
            if case .string(let s) = logVal { return s }
        }
        return nil
    }
}
