import SwiftUI

struct HestiaPanelModifier: ViewModifier {
    var cornerRadius: CGFloat = MacCornerRadius.panel
    @State private var isHovered = false

    func body(content: Content) -> some View {
        content
            .background(MacColors.panelBackground)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .strokeBorder(
                        isHovered ? MacColors.cardBorderStrong : MacColors.cardBorder,
                        lineWidth: 0.5
                    )
            )
            .onHover { hovering in
                withAnimation(MacAnimation.fastSpring) {
                    isHovered = hovering
                }
            }
    }
}

extension View {
    func hestiaPanel(cornerRadius: CGFloat = MacCornerRadius.panel) -> some View {
        modifier(HestiaPanelModifier(cornerRadius: cornerRadius))
    }
}
