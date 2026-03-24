import SwiftUI
import HestiaShared

struct MacWorkflowRow: View {
    let workflow: WorkflowSummary
    let isSelected: Bool

    var body: some View {
        HStack(spacing: MacSpacing.md) {
            // Status indicator
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(workflow.name)
                    .font(.system(size: 13, weight: isSelected ? .semibold : .regular))
                    .foregroundStyle(isSelected ? MacColors.textPrimary : MacColors.textSecondary)
                    .lineLimit(1)

                HStack(spacing: MacSpacing.sm) {
                    // Trigger type badge
                    Label(workflow.triggerType, systemImage: triggerIcon)
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)

                    // Node count
                    if workflow.runCount > 0 {
                        Text("\(workflow.runCount) runs")
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            }

            Spacer()

            // Status badge
            Text(workflow.status.capitalized)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(statusColor)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(statusColor.opacity(0.15))
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                .fill(isSelected ? MacColors.activeTabBackground : Color.clear)
        )
    }

    // MARK: - Helpers

    private var statusColor: Color {
        switch workflow.statusEnum {
        case .active: return MacColors.healthGreen
        case .draft: return MacColors.amberAccent
        case .inactive: return MacColors.textFaint
        case .archived: return MacColors.textFaint.opacity(0.5)
        }
    }

    private var triggerIcon: String {
        switch workflow.triggerTypeEnum {
        case .manual: return "hand.tap"
        case .schedule: return "clock"
        }
    }
}
