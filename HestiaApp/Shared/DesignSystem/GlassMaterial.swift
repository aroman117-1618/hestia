import SwiftUI

// MARK: - Glass Surface Types

/// Defines the visual treatment for different glass surfaces.
/// Currently uses simulated glass (solid background + luminous border).
/// NOTE: macOS 26+ can use native `.glassEffect()` behind `#available` checks
/// when the deployment target is raised.
enum GlassSurface {
    case sidebar     // Deep background, faint amber tint
    case chatPanel   // Slightly lighter, minimal tint
    case toolbar     // Thin material feel, no amber tint
    case card        // Simulated: bg.elevated + luminous border
    case input       // Input field surface, subtle amber warmth
}

// MARK: - Glass Material Modifier

/// Applies simulated glass material to any view.
/// Adds a background fill and a subtle luminous border appropriate
/// for the specified surface type.
struct GlassMaterialModifier: ViewModifier {
    let surface: GlassSurface

    func body(content: Content) -> some View {
        content
            .background(backgroundColor)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .strokeBorder(borderColor, lineWidth: 0.5)
            )
    }

    // MARK: - Surface Properties

    private var backgroundColor: Color {
        #if os(macOS)
        switch surface {
        case .sidebar:   return MacColors.sidebarBackground
        case .chatPanel: return MacColors.panelBackground
        case .toolbar:   return MacColors.windowBackground
        case .card:      return MacColors.panelBackground
        case .input:     return MacColors.chatInputBackground
        }
        #else
        switch surface {
        case .sidebar:   return Color(hex: "1A1A1C")
        case .chatPanel: return Color(hex: "1C1C1E")
        case .toolbar:   return Color(hex: "161618")
        case .card:      return Color.iosCardBackground
        case .input:     return Color.iosCardBackground
        }
        #endif
    }

    private var borderColor: Color {
        #if os(macOS)
        switch surface {
        case .sidebar:   return MacColors.sidebarBorder
        case .chatPanel: return MacColors.subtleBorder
        case .toolbar:   return MacColors.divider
        case .card:      return MacColors.cardBorder
        case .input:     return MacColors.cardBorder
        }
        #else
        switch surface {
        case .sidebar:   return Color(hex: "FF9F0A").opacity(0.08)
        case .chatPanel: return Color(hex: "FF9F0A").opacity(0.06)
        case .toolbar:   return Color.white.opacity(0.06)
        case .card:      return Color(hex: "FF9F0A").opacity(0.08)
        case .input:     return Color(hex: "FF9F0A").opacity(0.10)
        }
        #endif
    }

    private var cornerRadius: CGFloat {
        switch surface {
        case .sidebar:   return 0
        case .chatPanel: return 0
        case .toolbar:   return 0
        case .card:      return GlassRadius.lg
        case .input:     return GlassRadius.capsule
        }
    }
}

// MARK: - View Extension

extension View {
    /// Applies a simulated glass material treatment.
    func glassMaterial(_ surface: GlassSurface) -> some View {
        modifier(GlassMaterialModifier(surface: surface))
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        Text("Card Surface")
            .foregroundStyle(.white)
            .padding()
            .frame(maxWidth: .infinity)
            .glassMaterial(.card)

        Text("Input Surface")
            .foregroundStyle(.white)
            .padding()
            .frame(maxWidth: .infinity)
            .glassMaterial(.input)

        Text("Toolbar Surface")
            .foregroundStyle(.white)
            .padding()
            .frame(maxWidth: .infinity)
            .glassMaterial(.toolbar)
    }
    .padding()
    .background(Color.black)
}
