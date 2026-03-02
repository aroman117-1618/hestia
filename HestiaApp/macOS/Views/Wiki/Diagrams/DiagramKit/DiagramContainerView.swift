import SwiftUI

struct DiagramContainerView<Content: View>: View {
    let title: String
    var subtitle: String? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.sm) {
                Text(title)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textFaint)
                }
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.top, MacSpacing.md)

            content()
                .frame(minHeight: 200)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.bottom, MacSpacing.md)
        }
        .background(MacColors.panelBackground)
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
    }
}
