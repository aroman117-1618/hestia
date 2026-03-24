import SwiftUI
import HestiaShared

struct MacWorkflowNodeRow: View {
    let node: WorkflowNodeResponse

    var body: some View {
        HStack(spacing: MacSpacing.md) {
            // Node type icon
            Image(systemName: node.iconName)
                .font(.system(size: 13))
                .foregroundStyle(MacColors.amberAccent)
                .frame(width: 28, height: 28)
                .background(MacColors.activeTabBackground)
                .clipShape(RoundedRectangle(cornerRadius: 6))

            VStack(alignment: .leading, spacing: 1) {
                Text(node.label)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                Text(nodeTypeLabel)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }

            Spacer()

            // Config indicator
            if !node.config.isEmpty {
                Image(systemName: "gearshape")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
    }

    private var nodeTypeLabel: String {
        switch node.nodeTypeEnum {
        case .runPrompt: return "Run Prompt"
        case .callTool: return "Call Tool"
        case .notify: return "Notification"
        case .log: return "Log"
        case .ifElse: return "Condition"
        case .schedule: return "Schedule Trigger"
        case .manual: return "Manual Trigger"
        }
    }
}
