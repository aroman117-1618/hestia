import SwiftUI
import HestiaShared

struct MacMessageInputBar: View {
    @Binding var messageText: String
    @EnvironmentObject var appState: AppState
    @FocusState private var isInputFocused: Bool
    @State private var showCommandPicker = false
    @State private var sendTrigger = false
    @State private var sendPulseScale: CGFloat = 1.0
    let onSend: () -> Void

    private var isEmpty: Bool {
        messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        HStack(spacing: MacSpacing.sm) {
            // Commands
            Button { showCommandPicker.toggle() } label: {
                Image(systemName: "terminal")
                    .font(.system(size: 15))
                    .foregroundStyle(showCommandPicker ? MacColors.amberAccent : MacColors.textSecondary)
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.hestiaIcon)
            .popover(isPresented: $showCommandPicker, arrowEdge: .top) {
                CommandPickerView { command in
                    messageText = command
                    showCommandPicker = false
                    isInputFocused = true
                }
            }
            .accessibilityLabel("Commands")

            // Text field
            TextField("Message \(appState.currentMode.displayName)...", text: $messageText)
                .font(MacTypography.inputField)
                .textFieldStyle(.plain)
                .foregroundStyle(MacColors.textPrimary)
                .focused($isInputFocused)
                .onSubmit(handleSend)

            // Mic
            Button {} label: {
                Image(systemName: "mic")
                    .font(.system(size: 15))
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.hestiaIcon)
            .accessibilityLabel("Voice input")

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
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .contentShape(Capsule())
        .onTapGesture { isInputFocused = true }
        .clipShape(Capsule())
        // Focus glow — amber border fades in when input is active
        .overlay {
            Capsule()
                .strokeBorder(
                    MacColors.amberAccent.opacity(isInputFocused ? 0.5 : 0),
                    lineWidth: 1.5
                )
                .animation(.easeInOut(duration: 0.2), value: isInputFocused)
        }
        .padding(.horizontal, 33)
        .padding(.vertical, MacSpacing.lg)
        .background(MacColors.chatInputBackground)
        // Haptic feedback on message send
        .sensoryFeedback(.success, trigger: sendTrigger)
    }

    private func handleSend() {
        guard !isEmpty else { return }
        // Send pulse: scale 1.0 → 1.12 → 1.0
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
