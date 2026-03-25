import SwiftUI

/// A small pill badge representing a cross-module link from a Research entity
/// to another Hestia feature (workflow, chat, command, canvas).
///
/// Tapping the badge triggers the optional `onTap` callback, which callers
/// use to drive navigation via the deep link system.
struct HestiaCrossLinkBadge: View {
    let module: String       // "workflow", "chat", "command", "research_canvas"
    let itemId: String
    let context: String      // Short description shown in the pill
    var onTap: (() -> Void)? = nil

    private var moduleIcon: String {
        switch module {
        case "workflow": return "arrow.triangle.branch"
        case "chat": return "bubble.left"
        case "command": return "house"
        case "research_canvas": return "rectangle.3.group"
        default: return "link"
        }
    }

    private var moduleColor: Color {
        MacColors.amberAccent
    }

    var body: some View {
        Button(action: { onTap?() }) {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: moduleIcon)
                    .font(.system(size: 10))
                    .foregroundColor(moduleColor)
                Text(context)
                    .font(MacTypography.caption)
                    .foregroundColor(MacColors.textSecondary)
                    .lineLimit(1)
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
            .background(moduleColor.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
            .overlay(
                RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                    .strokeBorder(moduleColor.opacity(0.12), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}
