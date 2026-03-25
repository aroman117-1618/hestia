import SwiftUI
import HestiaShared

/// Extracted input bar with three-mode support: chat, voice conversation, voice journal.
/// Mode toggle (left icon) cycles through modes; input field and action button adapt per mode.
struct ChatInputBar: View {
    @Binding var messageText: String
    @Binding var inputMode: ChatInputMode
    var isInputFocused: FocusState<Bool>.Binding
    let isLoading: Bool
    let isRecording: Bool
    let audioLevel: CGFloat
    let forceLocal: Bool
    let currentModeName: String
    let onSend: (String) -> Void
    let onToggleLocal: () -> Void
    let onStartVoice: () -> Void

    var body: some View {
        HStack(spacing: Spacing.md) {
            modeToggleButton
            privateToggleButton

            if isRecording {
                recordingIndicator
            } else {
                textField
            }

            actionButton
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
        .background(Color.black.opacity(0.3))
    }

    // MARK: - Mode Toggle

    private var modeToggleButton: some View {
        Button {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                inputMode = inputMode.next
            }
        } label: {
            Image(systemName: inputMode.icon)
                .font(.system(size: 18, weight: .medium))
                .foregroundColor(inputMode.color)
                .frame(width: 32, height: 32)
                .background(inputMode.color.opacity(0.15))
                .clipShape(Circle())
        }
        .accessibilityLabel("\(inputMode.rawValue.capitalized) mode")
        .accessibilityHint("Tap to switch to \(inputMode.next.rawValue) mode. Long press for picker.")
        .contextMenu {
            ForEach(ChatInputMode.allCases) { mode in
                Button {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                        inputMode = mode
                    }
                } label: {
                    Label(mode.rawValue.capitalized, systemImage: mode.icon)
                }
            }
        }
    }

    // MARK: - Private Toggle

    private var privateToggleButton: some View {
        Button(action: onToggleLocal) {
            Image(systemName: forceLocal ? "lock.fill" : "lock.open")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(forceLocal ? .warningYellow : .white.opacity(0.4))
        }
        .accessibilityLabel(forceLocal ? "Private mode on" : "Private mode off")
        .accessibilityHint("Toggle private mode to keep this message local")
    }

    // MARK: - Text Field

    private var textField: some View {
        TextField(placeholderText, text: $messageText)
            .font(.inputField)
            .foregroundColor(.white)
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.sm)
            .background(Color.white.opacity(0.15))
            .cornerRadius(CornerRadius.input)
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.input)
                    .stroke(inputMode == .chat ? Color.clear : inputMode.color.opacity(0.3), lineWidth: 1)
            )
            .focused(isInputFocused)
            .submitLabel(.send)
            .onSubmit {
                guard canSend else { return }
                onSend(messageText)
            }
            .accessibilityLabel("Message input")
            .accessibilityHint("Type your message to \(currentModeName)")
    }

    // MARK: - Recording Indicator (replaces text field during recording)

    private var recordingIndicator: some View {
        HStack(spacing: Spacing.sm) {
            WaveformView(audioLevel: audioLevel, tintColor: inputMode.color)
            Text("Listening...")
                .font(.caption)
                .foregroundColor(inputMode.color.opacity(0.8))
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.sm)
        .background(inputMode.color.opacity(0.08))
        .cornerRadius(CornerRadius.input)
    }

    // MARK: - Action Button (send / mic)

    @ViewBuilder
    private var actionButton: some View {
        if canSend {
            Button { onSend(messageText) } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundColor(forceLocal ? .warningYellow : inputMode == .chat ? .white : inputMode.color)
            }
            .accessibilityLabel("Send message")
        } else if inputMode != .chat {
            // Voice/Journal mode: prominent mic button
            Button {
                onStartVoice()
            } label: {
                Image(systemName: "mic.fill")
                    .font(.system(size: 20))
                    .foregroundColor(inputMode.color)
                    .frame(width: 36, height: 36)
                    .background(inputMode.color.opacity(0.15))
                    .clipShape(Circle())
            }
            .disabled(isLoading)
            .accessibilityLabel("Start \(inputMode.rawValue) recording")
            .accessibilityHint("Tap to start \(inputMode.rawValue) recording")
        } else {
            // Chat mode: subtle mic button (existing behavior)
            Button {
                onStartVoice()
            } label: {
                Image(systemName: "mic.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.white.opacity(0.7))
                    .frame(width: 32, height: 32)
            }
            .disabled(isLoading)
            .accessibilityLabel("Voice input")
            .accessibilityHint("Tap to start voice recording")
        }
    }

    // MARK: - Computed

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    private var placeholderText: String {
        if forceLocal {
            return "Private — stays local..."
        }
        return "\(inputMode.placeholder) \(currentModeName)..."
    }
}
