import SwiftUI

// MARK: - Glass Card Variants

enum GlassCardVariant {
    case `default`
    case accent       // 2pt left amber border
    case interactive  // press scale 0.98x
}

// MARK: - Glass Card

/// Generic container view with glass material background and optional label.
/// Supports default, accent (left border), and interactive (hover scale) variants.
struct HestiaGlassCard<Content: View>: View {
    let label: String?
    let variant: GlassCardVariant
    @ViewBuilder let content: () -> Content
    @State private var isHovered = false

    init(
        label: String? = nil,
        variant: GlassCardVariant = .default,
        @ViewBuilder content: @escaping () -> Content
    ) {
        self.label = label
        self.variant = variant
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: GlassSpacing.sm) {
            if let label {
                Text(label)
                    .font(.system(size: 11, weight: .semibold))
                    .tracking(0.8)
                    .textCase(.uppercase)
                    .foregroundStyle(glassTextTertiary)
            }
            content()
        }
        .padding(GlassSpacing.md)
        .background(glassElevated)
        .clipShape(RoundedRectangle(cornerRadius: GlassRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: GlassRadius.lg)
                .strokeBorder(isHovered ? glassBorderDefault : glassBorderSubtle, lineWidth: 0.5)
        )
        .overlay(alignment: .leading) {
            if variant == .accent {
                RoundedRectangle(cornerRadius: 1)
                    .fill(glassAccent)
                    .frame(width: 2)
                    .padding(.vertical, GlassSpacing.sm)
            }
        }
        .scaleEffect(isHovered && variant != .default ? 1.005 : 1.0)
        .onHover { hovering in
            withAnimation(.spring(response: 0.2, dampingFraction: 0.85)) {
                isHovered = hovering
            }
        }
    }

    // MARK: - Platform-Resolved Colors

    private var glassElevated: Color {
        #if os(macOS)
        MacColors.panelBackground
        #else
        Color.iosCardBackground
        #endif
    }

    private var glassBorderSubtle: Color {
        #if os(macOS)
        MacColors.subtleBorder
        #else
        Color(hex: "FF9F0A").opacity(0.06)
        #endif
    }

    private var glassBorderDefault: Color {
        #if os(macOS)
        MacColors.cardBorder
        #else
        Color(hex: "FF9F0A").opacity(0.12)
        #endif
    }

    private var glassAccent: Color {
        #if os(macOS)
        MacColors.amberAccent
        #else
        Color.agentAmber
        #endif
    }

    private var glassTextTertiary: Color {
        #if os(macOS)
        MacColors.textPlaceholder
        #else
        Color.white.opacity(0.4)
        #endif
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        HestiaGlassCard(label: "Default Card") {
            Text("Content goes here")
                .foregroundStyle(.white)
        }

        HestiaGlassCard(label: "Accent Card", variant: .accent) {
            Text("With amber left border")
                .foregroundStyle(.white)
        }

        HestiaGlassCard(variant: .interactive) {
            Text("Interactive — hover to scale")
                .foregroundStyle(.white)
        }
    }
    .padding()
    .background(Color.black)
}
