import SwiftUI
import HestiaShared

/// Reusable card container for the mobile UI.
/// Dark background, subtle border, 14px radius, optional section label.
struct HestiaCard<Content: View>: View {
    let label: String?
    let content: Content

    init(label: String? = nil, @ViewBuilder content: () -> Content) {
        self.label = label
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let label = label {
                Text(label.uppercased())
                    .font(.caption2.weight(.semibold))
                    .foregroundColor(.white.opacity(0.4))
                    .tracking(0.8)
                    .padding(.horizontal, Spacing.md)
                    .padding(.bottom, Spacing.sm)
            }

            content
                .padding(Spacing.md)
                .background(Color.iosCardBackground)
                .cornerRadius(14)
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(Color.iosCardBorder, lineWidth: 0.5)
                )
        }
    }
}
