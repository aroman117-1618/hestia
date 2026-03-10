import SwiftUI
import HestiaShared

struct MacMessageInputBar: View {
    @Binding var messageText: String
    @EnvironmentObject var appState: AppState
    @State private var sendTrigger = false
    @State private var sendPulseScale: CGFloat = 1.0
    /// History state for CLI recall (up/down arrow)
    @State private var history: [String] = []
    @State private var historyIndex: Int? = nil
    /// Reported content height from CLITextView
    @State private var textContentHeight: CGFloat = 36

    let onSend: () -> Void

    private var isEmpty: Bool {
        messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// Clamped text view height: single line when empty, grows with content, caps at 200
    private var clampedHeight: CGFloat {
        min(max(textContentHeight, 36), 200)
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: MacSpacing.sm) {
            // Text view (history recall, multi-line, amber cursor)
            CLITextView(
                text: $messageText,
                placeholder: "Message Hestia...",
                promptChar: "",
                onSend: handleSend,
                onEscape: { /* clear handled inside CLITextView */ },
                history: $history,
                historyIndex: $historyIndex,
                contentHeight: $textContentHeight
            )
            .frame(width: nil, height: clampedHeight)
            .frame(maxWidth: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // Send button with pulse micro-interaction
            Button(action: handleSend) {
                Image(systemName: "paperplane.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.buttonTextDark)
                    .frame(width: 28, height: 28)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.hestia)
            .scaleEffect(sendPulseScale)
            .disabled(isEmpty)
            .opacity(isEmpty ? 0.5 : 1)
            .accessibilityLabel("Send message")
            .padding(.bottom, 4)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        // Focus glow — amber border fades in when content is being composed
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    MacColors.amberAccent.opacity(!isEmpty ? 0.4 : 0),
                    lineWidth: 1.5
                )
                .animation(.easeInOut(duration: 0.2), value: isEmpty)
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.chatInputBackground)
        // Haptic feedback on message send
        .sensoryFeedback(.success, trigger: sendTrigger)
    }

    private func handleSend() {
        guard !isEmpty else { return }
        // Send pulse: scale 1.0 -> 1.12 -> 1.0
        withAnimation(.spring(response: 0.15, dampingFraction: 0.5)) {
            sendPulseScale = 1.12
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            withAnimation(.spring(response: 0.2, dampingFraction: 0.7)) {
                sendPulseScale = 1.0
            }
        }
        sendTrigger.toggle()
        onSend()
    }
}
