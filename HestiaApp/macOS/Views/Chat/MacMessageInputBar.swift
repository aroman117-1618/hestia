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

    // Recording state
    @State private var isRecording = false
    @State private var recordingStartTime: Date?
    @State private var recordingTimer: Timer?
    @State private var recordingTick: Int = 0

    // Session controls
    let hasMessages: Bool
    let sessionId: String?
    let onMoveToBackground: (String) async -> Void
    let onNewSession: () -> Void

    let onSend: () -> Void

    private var isEmpty: Bool {
        messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// Clamped text view height: single line when empty, grows with content, caps at 200
    private var clampedHeight: CGFloat {
        min(max(textContentHeight, 36), 200)
    }

    private var recordingDuration: String {
        guard let start = recordingStartTime else { return "0:00" }
        let elapsed = Int(Date().timeIntervalSince(start))
        return String(format: "%d:%02d", elapsed / 60, elapsed % 60)
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: MacSpacing.sm) {
            // Text view or recording indicator
            if isRecording {
                HStack(spacing: MacSpacing.sm) {
                    Circle()
                        .fill(MacColors.healthRed)
                        .frame(width: 8, height: 8)
                    Text("Listening...")
                        .font(MacTypography.chatMessage)
                        .foregroundStyle(MacColors.textPrimary)
                    Text(recordingDuration)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textSecondary)
                    Spacer()
                }
                .frame(height: 36)
                .frame(maxWidth: .infinity)
            } else {
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
            }

            // Right-side buttons
            HStack(spacing: MacSpacing.xs) {
                // Session button (always visible)
                BackgroundSessionButton(
                    hasMessages: hasMessages,
                    sessionId: sessionId,
                    onMoveToBackground: onMoveToBackground,
                    onNewSession: onNewSession
                )
                .frame(width: 24, height: 24)

                // Mic/Send swap
                if isRecording {
                    // Stop button (red)
                    Button {
                        stopRecording()
                    } label: {
                        Image(systemName: "stop.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(.white)
                            .frame(width: 28, height: 28)
                            .background(MacColors.healthRed)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.hestia)
                    .accessibilityLabel("Stop recording")
                    .padding(.bottom, 4)
                } else if isEmpty {
                    // Mic button
                    Button {
                        startRecording()
                    } label: {
                        Image(systemName: "mic.fill")
                            .font(.system(size: 14))
                            .foregroundStyle(MacColors.amberAccent)
                            .frame(width: 28, height: 28)
                            .background(MacColors.amberAccent.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.hestia)
                    .accessibilityLabel("Start recording")
                    .padding(.bottom, 4)
                } else {
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
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        // Focus glow — amber border when composing, red when recording
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isRecording
                        ? MacColors.healthRed.opacity(0.4)
                        : MacColors.amberAccent.opacity(!isEmpty ? 0.4 : 0),
                    lineWidth: 1.5
                )
                .animation(.easeInOut(duration: 0.2), value: isEmpty)
                .animation(.easeInOut(duration: 0.2), value: isRecording)
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.chatInputBackground)
        // Haptic feedback on message send
        .sensoryFeedback(.success, trigger: sendTrigger)
    }

    // MARK: - Actions

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

    private func startRecording() {
        isRecording = true
        recordingStartTime = Date()
        recordingTick = 0
        recordingTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            recordingTick += 1
        }
    }

    private func stopRecording() {
        isRecording = false
        recordingTimer?.invalidate()
        recordingTimer = nil
        recordingStartTime = nil
        recordingTick = 0
    }
}
