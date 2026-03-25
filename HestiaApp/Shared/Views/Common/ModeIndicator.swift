import SwiftUI
import HestiaShared

/// Displays the current mode with a colored indicator
struct ModeIndicator: View {
    let mode: HestiaMode
    var onTap: (() -> Void)?

    var body: some View {
        Button(action: { onTap?() }) {
            HStack(spacing: Spacing.xs) {
                // Status dot
                Circle()
                    .fill(Color.accent)
                    .frame(width: 8, height: 8)

                // Mode name
                Text(mode.displayName)
                    .font(.modeLabel)
                    .foregroundColor(.textPrimary.opacity(0.9))
            }
            .padding(.horizontal, Spacing.sm)
            .padding(.vertical, Spacing.xs)
            .background(Color.bgOverlay)
            .cornerRadius(CornerRadius.small)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Current mode: \(mode.displayName)")
        .accessibilityHint(onTap != nil ? "Double tap to change mode" : "")
    }
}

/// Larger mode selector for settings/mode picker
struct ModeSelector: View {
    @Binding var selectedMode: HestiaMode
    let onModeChange: ((HestiaMode) -> Void)?

    var body: some View {
        HStack(spacing: Spacing.sm) {
            ForEach(HestiaMode.allCases) { mode in
                ModeSelectorButton(
                    mode: mode,
                    isSelected: mode == selectedMode,
                    action: {
                        withAnimation(.hestiaStandard) {
                            selectedMode = mode
                        }
                        onModeChange?(mode)
                    }
                )
            }
        }
    }
}

/// Individual mode button in the selector
struct ModeSelectorButton: View {
    let mode: HestiaMode
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: Spacing.xs) {
                // Mode icon/avatar
                Circle()
                    .fill(isSelected ? Color.accent : Color.textPrimary.opacity(0.2))
                    .frame(width: 50, height: 50)
                    .overlay(
                        Text(mode.displayName.prefix(1))
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(isSelected ? .textPrimary : .textSecondary)
                    )

                // Mode name
                Text(mode.displayName)
                    .font(.caption)
                    .foregroundColor(isSelected ? .textPrimary : .textSecondary)
            }
            .padding(Spacing.sm)
            .background(isSelected ? Color.bgOverlay : Color.clear)
            .cornerRadius(CornerRadius.small)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(mode.displayName) mode")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Preview

struct ModeIndicator_Previews: PreviewProvider {
    struct PreviewWrapper: View {
        @State var mode: HestiaMode = .tia

        var body: some View {
            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 40) {
                    // Small indicator
                    ModeIndicator(mode: mode) {
                        #if DEBUG
                        print("Tapped mode indicator")
                        #endif
                    }

                    // Mode selector
                    ModeSelector(selectedMode: $mode) { newMode in
                        #if DEBUG
                        print("Selected: \(newMode)")
                        #endif
                    }
                }
            }
        }
    }

    static var previews: some View {
        PreviewWrapper()
    }
}
