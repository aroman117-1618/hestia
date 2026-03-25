import SwiftUI

/// Standardised list row with a leading indicator (colored dot or SF Symbol),
/// a title + optional subtitle, and an optional trailing label.
///
/// Used wherever sidebar rows appear: entities, boards, memories, articles, etc.
struct HestiaContentRow: View {
    let title: String
    var subtitle: String? = nil
    var dotColor: Color? = nil
    var systemImage: String? = nil
    var trailingText: String? = nil
    var isSelected: Bool = false
    var selectionAccent: Color = MacColors.amberAccent
    var action: (() -> Void)? = nil
    @State private var isHovered = false

    var body: some View {
        Button(action: { action?() }) {
            HStack(spacing: MacSpacing.sm) {
                leadingIndicator

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)
                    if let subtitle {
                        Text(subtitle)
                            .font(MacTypography.micro)
                            .foregroundStyle(MacColors.textFaint)
                            .lineLimit(1)
                    }
                }

                Spacer()

                if let trailingText {
                    Text(trailingText)
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.textFaint)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(MacColors.textPrimary.opacity(0.06))
                        .clipShape(Capsule())
                        .overlay(
                            Capsule()
                                .strokeBorder(MacColors.subtleBorder, lineWidth: 0.5)
                        )
                }
            }
            .padding(.vertical, 3)
            .padding(.horizontal, MacSpacing.sm)
            .background(
                isSelected
                    ? MacColors.panelBackground.opacity(0.5)
                    : (isHovered ? MacColors.panelBackground.opacity(0.25) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                    .strokeBorder(isSelected ? MacColors.subtleBorder : Color.clear, lineWidth: 0.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(MacAnimation.fastSpring) {
                isHovered = hovering
            }
        }
    }

    @ViewBuilder
    private var leadingIndicator: some View {
        if let dotColor {
            Circle()
                .fill(dotColor)
                .frame(width: 6, height: 6)
        } else if let systemImage {
            Image(systemName: systemImage)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 16)
        }
    }
}
