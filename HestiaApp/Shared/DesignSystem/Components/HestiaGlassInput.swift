import SwiftUI

/// Capsule-shaped text input with glass material styling.
/// Focus state transitions border color and adds an amber glow.
struct HestiaGlassInput<Trailing: View>: View {
    let placeholder: String
    @Binding var text: String
    let leadingIcon: String?
    @ViewBuilder let trailingContent: () -> Trailing
    @FocusState private var isFocused: Bool

    init(
        placeholder: String,
        text: Binding<String>,
        leadingIcon: String? = nil,
        @ViewBuilder trailingContent: @escaping () -> Trailing
    ) {
        self.placeholder = placeholder
        self._text = text
        self.leadingIcon = leadingIcon
        self.trailingContent = trailingContent
    }

    var body: some View {
        HStack(spacing: GlassSpacing.sm) {
            if let leadingIcon {
                Image(systemName: leadingIcon)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(isFocused ? glassAccent : glassTextTertiary)
            }

            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .foregroundStyle(glassTextPrimary)
                .focused($isFocused)

            trailingContent()
        }
        .padding(.horizontal, GlassSpacing.lg)
        .frame(height: 44)
        .background(glassInputBackground)
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .strokeBorder(isFocused ? glassAccent : glassBorderDefault, lineWidth: 0.5)
        )
        .shadow(color: isFocused ? glassAccent.opacity(0.15) : .clear, radius: 8, y: 0)
    }

    // MARK: - Platform-Resolved Colors

    private var glassInputBackground: Color {
        #if os(macOS)
        MacColors.chatInputBackground
        #else
        Color.iosCardBackground
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

    private var glassTextPrimary: Color {
        #if os(macOS)
        MacColors.textPrimary
        #else
        Color.white
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

// MARK: - Convenience Init (no trailing content)

extension HestiaGlassInput where Trailing == EmptyView {
    init(
        placeholder: String,
        text: Binding<String>,
        leadingIcon: String? = nil
    ) {
        self.placeholder = placeholder
        self._text = text
        self.leadingIcon = leadingIcon
        self.trailingContent = { EmptyView() }
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        HestiaGlassInput(
            placeholder: "Search...",
            text: .constant(""),
            leadingIcon: "magnifyingglass"
        )

        HestiaGlassInput(
            placeholder: "Enter command",
            text: .constant("Hello world")
        )
    }
    .padding()
    .background(Color.black)
}
