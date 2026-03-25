import SwiftUI
import HestiaShared

/// Input bar for composing messages
struct MessageInputBar: View {
    @Binding var text: String
    let mode: HestiaMode
    let isLoading: Bool
    let onSend: () -> Void

    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Text field
            TextField(placeholder, text: $text)
                .font(.inputField)
                .foregroundColor(.textPrimary)
                .padding(.horizontal, Spacing.md)
                .padding(.vertical, Spacing.sm)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.input)
                .focused($isFocused)
                .submitLabel(.send)
                .onSubmit {
                    if canSend {
                        onSend()
                    }
                }
                .accessibilityLabel("Message input")
                .accessibilityHint("Type your message to \(mode.displayName)")

            // Send button
            Button(action: {
                if canSend {
                    isFocused = false
                    onSend()
                }
            }) {
                ZStack {
                    Circle()
                        .fill(canSend ? Color.textPrimary.opacity(0.9) : Color.textPrimary.opacity(0.2))
                        .frame(width: 36, height: 36)

                    Image(systemName: "arrow.up")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(canSend ? .accent : .textSecondary)
                }
            }
            .disabled(!canSend)
            .accessibilityLabel(canSend ? "Send message" : "Cannot send")
            .accessibilityHint(canSend ? "Double tap to send your message" : "Enter a message first")
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
        .background(Color.bgInput)
    }

    // MARK: - Computed Properties

    private var placeholder: String {
        "Message \(mode.displayName)..."
    }

    private var canSend: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    private var modeColor: Color {
        mode.gradientColors.first ?? .blue
    }
}

// MARK: - Preview

struct MessageInputBar_Previews: PreviewProvider {
    struct PreviewWrapper: View {
        @State var text = ""

        var body: some View {
            ZStack {
                Color.black.ignoresSafeArea()

                VStack {
                    Spacer()

                    MessageInputBar(
                        text: $text,
                        mode: .tia,
                        isLoading: false,
                        onSend: {
                            #if DEBUG
                            print("Sending: \(text)")
                            #endif
                            text = ""
                        }
                    )
                }
            }
        }
    }

    static var previews: some View {
        PreviewWrapper()
    }
}
