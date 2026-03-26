import SwiftUI
import HestiaShared

/// Liquid glass input bar: text field on left, voice/send on right.
/// Single tap mic = transcription mode, hold 2s = conversation mode.
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
    let onStartConversation: () -> Void

    @State private var holdProgress: CGFloat = 0
    @State private var holdTask: Task<Void, Never>?
    @State private var isHolding = false

    private static let holdDuration: TimeInterval = 2.0
    private static let holdTickInterval: TimeInterval = 0.05

    var body: some View {
        HStack(spacing: 12) {
            // Private mode toggle
            privateToggleButton

            if isRecording {
                recordingIndicator
            } else {
                textField
            }

            // Action button: send (when text present) or mic (when empty)
            actionButton
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(Color.white.opacity(0.08))
                .background(
                    RoundedRectangle(cornerRadius: 24)
                        .fill(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
                )
        )
        .padding(.horizontal, 12)
        .padding(.bottom, 8)
    }

    // MARK: - Private Toggle

    private var privateToggleButton: some View {
        Button(action: onToggleLocal) {
            Image(systemName: forceLocal ? "lock.fill" : "lock.open")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(forceLocal ? .warningYellow : .white.opacity(0.4))
        }
        .accessibilityLabel(forceLocal ? "Private mode on" : "Private mode off")
    }

    // MARK: - Text Field

    private var textField: some View {
        TextField(placeholderText, text: $messageText)
            .font(.system(size: 16))
            .foregroundColor(.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .focused(isInputFocused)
            .submitLabel(.send)
            .onSubmit {
                guard canSend else { return }
                onSend(messageText)
            }
            .accessibilityLabel("Message input")
    }

    // MARK: - Recording Indicator

    private var recordingIndicator: some View {
        HStack(spacing: 8) {
            WaveformView(audioLevel: audioLevel, tintColor: Color(hex: "FF9F0A"))
            Text("Listening...")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "FF9F0A").opacity(0.8))
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Action Button

    @ViewBuilder
    private var actionButton: some View {
        if canSend {
            // Send button (amber arrow)
            Button { onSend(messageText) } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundColor(Color(hex: "FF9F0A"))
            }
            .accessibilityLabel("Send message")
        } else {
            // Mic button with tap/hold
            micButton
        }
    }

    private var micButton: some View {
        ZStack {
            // Progress ring (visible during hold)
            if holdProgress > 0 {
                Circle()
                    .trim(from: 0, to: holdProgress)
                    .stroke(Color(hex: "FF9F0A"), style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .frame(width: 38, height: 38)
            }

            Image(systemName: "waveform")
                .font(.system(size: 18, weight: .medium))
                .foregroundColor(.white.opacity(0.7))
                .frame(width: 36, height: 36)
        }
        .contentShape(Circle())
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    if !isHolding {
                        isHolding = true
                        startHoldTimer()
                    }
                }
                .onEnded { _ in
                    let wasHolding = holdProgress >= 1.0
                    cancelHoldTimer()

                    if wasHolding {
                        // Hold completed: conversation mode
                        // Haptic already fired in timer
                    } else {
                        // Short tap: transcription mode
                        onStartVoice()
                    }
                }
        )
        .disabled(isLoading)
        .accessibilityLabel("Voice input")
        .accessibilityHint("Tap for transcription, hold for conversation mode")
    }

    // MARK: - Hold Timer

    private func startHoldTimer() {
        holdProgress = 0
        let totalTicks = Self.holdDuration / Self.holdTickInterval
        let increment = 1.0 / CGFloat(totalTicks)
        let tickNanos = UInt64(Self.holdTickInterval * 1_000_000_000)

        holdTask = Task { @MainActor in
            while !Task.isCancelled && holdProgress < 1.0 {
                try? await Task.sleep(nanoseconds: tickNanos)
                guard !Task.isCancelled else { return }
                holdProgress += increment

                if holdProgress >= 1.0 {
                    let generator = UIImpactFeedbackGenerator(style: .heavy)
                    generator.impactOccurred()
                    onStartConversation()
                    isHolding = false
                    holdProgress = 0
                    return
                }
            }
        }
    }

    private func cancelHoldTimer() {
        holdTask?.cancel()
        holdTask = nil
        isHolding = false
        withAnimation(.easeOut(duration: 0.2)) {
            holdProgress = 0
        }
    }

    // MARK: - Computed

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    private var placeholderText: String {
        if forceLocal {
            return "Private -- stays local..."
        }
        return "Message \(currentModeName)..."
    }
}
