import SwiftUI

/// Reusable collapsible sidebar section with an icon, title, and optional count badge.
///
/// Matches the `DisclosureGroup` pattern used in ResearchCanvasSidebar,
/// WikiSidebar, WorkflowSidebar, and ExplorerSidebar — any view that renders
/// a labelled, collapsible list with an item count.
struct HestiaSidebarSection<Content: View>: View {
    let title: String
    var icon: String? = nil
    var count: Int? = nil
    @Binding var isExpanded: Bool
    @ViewBuilder let content: () -> Content
    @State private var isHovered = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            content()
        } label: {
            HStack(spacing: MacSpacing.sm) {
                if let icon {
                    Image(systemName: icon)
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textSecondary)
                }
                Text(title)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                if let count, count > 0 {
                    Text("\(count)")
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
            .padding(.vertical, 2)
            .padding(.horizontal, MacSpacing.xs)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                    .fill(isHovered ? MacColors.panelBackground.opacity(0.3) : Color.clear)
            )
            .onHover { hovering in
                withAnimation(MacAnimation.fastSpring) {
                    isHovered = hovering
                }
            }
        }
        .tint(MacColors.textPlaceholder)
        .animation(MacAnimation.normalSpring, value: isExpanded)
    }
}
