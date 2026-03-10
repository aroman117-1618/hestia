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

    let onSend: () -> Void

    private var isEmpty: Bool {
        messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: MacSpacing.sm) {
            // CLI text view (preserves history recall, multi-line, amber cursor)
            CLITextView(
                text: $messageText,
                placeholder: "Message Hestia...",
                promptChar: "",
                onSend: handleSend,
                onEscape: { /* clear handled inside CLITextView */ },
                history: $history,
                historyIndex: $historyIndex
            )
            .frame(minHeight: 36, maxHeight: 200)
            .frame(maxWidth: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // Send button with pulse micro-interaction
            Button(action: handleSend) {
                Image(systemName: "paperplane.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.buttonTextDark)
                    .frame(width: MacSize.sendButtonSize, height: MacSize.sendButtonSize)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.sendButton))
            }
            .buttonStyle(.hestia)
            .scaleEffect(sendPulseScale)
            .disabled(isEmpty)
            .opacity(isEmpty ? 0.5 : 1)
            .accessibilityLabel("Send message")
            .padding(.bottom, 6)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        // Focus glow — amber border fades in when content is being composed
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(
                    MacColors.amberAccent.opacity(!isEmpty ? 0.4 : 0),
                    lineWidth: 1.5
                )
                .animation(.easeInOut(duration: 0.2), value: isEmpty)
        }
        .padding(.horizontal, 33)
        .padding(.vertical, MacSpacing.lg)
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
