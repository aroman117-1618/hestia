import SwiftUI

struct HestiaPanelModifier: ViewModifier {
    var cornerRadius: CGFloat = MacCornerRadius.panel

    func body(content: Content) -> some View {
        content
            .background(MacColors.panelBackground)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            )
    }
}

extension View {
    func hestiaPanel(cornerRadius: CGFloat = MacCornerRadius.panel) -> some View {
        modifier(HestiaPanelModifier(cornerRadius: cornerRadius))
    }
}
