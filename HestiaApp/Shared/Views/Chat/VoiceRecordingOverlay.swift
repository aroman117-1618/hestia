import SwiftUI

/// Overlay shown during voice recording with pulsing animation and live transcript.
struct VoiceRecordingOverlay: View {
    @ObservedObject var viewModel: VoiceInputViewModel
    let onStop: () -> Void
    let onCancel: () -> Void

    @State private var isPulsing = false

    var body: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            // Live transcript preview
            if !viewModel.currentLiveTranscript.isEmpty {
                Text(viewModel.currentLiveTranscript)
                    .font(.body)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
                    .padding(.horizontal, Spacing.xl)
                    .animation(.easeInOut(duration: 0.2), value: viewModel.currentLiveTranscript)
            } else {
                Text("Listening...")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.5))
            }

            // Pulsing mic indicator
            ZStack {
                // Outer pulse ring
                Circle()
                    .fill(Color.red.opacity(0.15))
                    .frame(width: 120, height: 120)
                    .scaleEffect(isPulsing ? 1.3 : 1.0)
                    .opacity(isPulsing ? 0.0 : 0.5)

                // Inner ring
                Circle()
                    .fill(Color.red.opacity(0.25))
                    .frame(width: 88, height: 88)

                // Mic icon
                Image(systemName: "mic.fill")
                    .font(.system(size: 36))
                    .foregroundColor(.white)
            }
            .onAppear {
                withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: false)) {
                    isPulsing = true
                }
            }

            // Duration
            Text(formattedDuration)
                .font(.system(size: 20, weight: .medium, design: .monospaced))
                .foregroundColor(.white)

            // Buttons
            HStack(spacing: Spacing.xl) {
                // Cancel
                Button(action: onCancel) {
                    VStack(spacing: Spacing.xs) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 44))
                            .foregroundColor(.white.opacity(0.6))
                        Text("Cancel")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }
                }

                // Stop
                Button(action: onStop) {
                    VStack(spacing: Spacing.xs) {
                        Image(systemName: "stop.circle.fill")
                            .font(.system(size: 56))
                            .foregroundColor(.red)
                        Text("Done")
                            .font(.caption)
                            .foregroundColor(.white)
                    }
                }
            }

            Spacer()
                .frame(height: Spacing.xl)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.85))
    }

    private var formattedDuration: String {
        let seconds = Int(viewModel.recordingDuration)
        let minutes = seconds / 60
        let remaining = seconds % 60
        return String(format: "%d:%02d", minutes, remaining)
    }
}
