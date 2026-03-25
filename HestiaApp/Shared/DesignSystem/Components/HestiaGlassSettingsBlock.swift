import SwiftUI

/// Notion-style navigation row with icon, title, subtitle, and chevron.
/// Glass material background with hover state.
struct HestiaGlassSettingsBlock<Destination: View>: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String?
    let destination: Destination?
    @State private var isHovered = false

    init(
        icon: String,
        iconColor: Color,
        title: String,
        subtitle: String? = nil,
        @ViewBuilder destination: () -> Destination
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.destination = destination()
    }

    var body: some View {
        if let destination {
            NavigationLink(destination: destination) {
                blockContent
            }
            .buttonStyle(.plain)
        } else {
            blockContent
        }
    }

    private var blockContent: some View {
        HStack(spacing: GlassSpacing.md) {
            // Icon in tinted frame
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundStyle(iconColor)
                .frame(width: 36, height: 36)
                .background(iconColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: GlassRadius.sm))

            // Text stack
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(glassTextPrimary)
                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 12))
                        .foregroundStyle(glassTextSecondary)
                }
            }

            Spacer()

            // Chevron
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(glassTextTertiary)
        }
        .padding(GlassSpacing.md)
        .background(glassElevated)
        .clipShape(RoundedRectangle(cornerRadius: GlassRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: GlassRadius.lg)
                .strokeBorder(isHovered ? glassBorderDefault : glassBorderSubtle, lineWidth: 0.5)
        )
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

    private var glassTextPrimary: Color {
        #if os(macOS)
        MacColors.textPrimary
        #else
        Color.white
        #endif
    }

    private var glassTextSecondary: Color {
        #if os(macOS)
        MacColors.textSecondary
        #else
        Color.white.opacity(0.5)
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

// MARK: - Non-Navigable Overload

extension HestiaGlassSettingsBlock where Destination == EmptyView {
    init(icon: String, iconColor: Color, title: String, subtitle: String? = nil) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.destination = nil
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 8) {
        HestiaGlassSettingsBlock(
            icon: "gear",
            iconColor: .gray,
            title: "General",
            subtitle: "App preferences"
        ) {
            Text("General Settings")
        }

        HestiaGlassSettingsBlock(
            icon: "brain.head.profile",
            iconColor: .purple,
            title: "Intelligence",
            subtitle: "Model routing & cloud"
        ) {
            Text("Intelligence Settings")
        }

        HestiaGlassSettingsBlock(
            icon: "shield.checkered",
            iconColor: .green,
            title: "Security"
        )
    }
    .padding()
    .background(Color.black)
}
