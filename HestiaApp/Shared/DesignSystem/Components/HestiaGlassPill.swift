import SwiftUI

/// Small tinted action button with glass styling.
/// Press animation scales to 0.96x with reduced opacity.
struct HestiaGlassPill: View {
    let title: String
    let icon: String?
    let tint: Color
    let action: () -> Void

    init(
        title: String,
        icon: String? = nil,
        tint: Color? = nil,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.icon = icon
        self.action = action

        #if os(macOS)
        self.tint = tint ?? MacColors.amberAccent
        #else
        self.tint = tint ?? Color.agentAmber
        #endif
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: GlassSpacing.xs) {
                if let icon {
                    Image(systemName: icon)
                        .font(.system(size: 14, weight: .medium))
                }
                Text(title)
                    .font(.system(size: 12, weight: .medium))
            }
            .foregroundStyle(tint)
            .padding(.vertical, 4)
            .padding(.horizontal, 12)
            .background(tint.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: GlassRadius.sm))
            .overlay(
                RoundedRectangle(cornerRadius: GlassRadius.sm)
                    .strokeBorder(tint.opacity(0.20), lineWidth: 0.5)
            )
        }
        .buttonStyle(GlassPillButtonStyle())
        .accessibilityLabel(title)
    }
}

// MARK: - Button Style

/// Custom button style that scales and fades on press.
private struct GlassPillButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.85), value: configuration.isPressed)
    }
}

// MARK: - Preview

#Preview {
    HStack(spacing: 12) {
        HestiaGlassPill(title: "Retry", icon: "arrow.clockwise") {}
        HestiaGlassPill(title: "Copy", icon: "doc.on.doc") {}
        HestiaGlassPill(title: "Error", icon: "exclamationmark.triangle", tint: .red) {}
    }
    .padding()
    .background(Color.black)
}
