import SwiftUI
import HestiaShared

/// Voice journal recording view — teal-themed flowing prose with serif typography.
/// Presented as a sheet when journal mode recording starts.
struct VoiceJournalView: View {
    @ObservedObject var voiceViewModel: VoiceInputViewModel
    let onSubmit: (String, TimeInterval) -> Void
    let onCancel: () -> Void
    @State private var cursorOpacity: Double = 1.0

    private let journalColor = Color.accent

    var body: some View {
        NavigationView {
            ZStack {
                Color.bgBase.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Header badge + timer
                    headerSection

                    Divider()
                        .background(journalColor.opacity(0.3))

                    // Transcript area
                    ScrollView {
                        transcriptSection
                            .padding(Spacing.lg)
                    }

                    Spacer()

                    // Bottom controls
                    controlsSection
                }
            }
            .navigationBarHidden(true)
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack {
            // Journal badge
            HStack(spacing: Spacing.xs) {
                Image(systemName: "book.fill")
                    .font(.system(size: 14))
                Text("Journal Entry")
                    .font(.caption.weight(.semibold))
            }
            .foregroundColor(journalColor)
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.xs)
            .background(journalColor.opacity(0.15))
            .cornerRadius(CornerRadius.button)

            Spacer()

            // Duration timer
            if voiceViewModel.isRecording {
                HStack(spacing: Spacing.xs) {
                    Circle()
                        .fill(Color.errorRed)
                        .frame(width: 8, height: 8)
                    Text(formatDuration(voiceViewModel.recordingDuration))
                        .font(.caption.monospacedDigit())
                        .foregroundColor(.textSecondary)
                }
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
    }

    // MARK: - Transcript

    private var transcriptSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            if voiceViewModel.rawTranscript.isEmpty && voiceViewModel.isRecording {
                Text("Listening...")
                    .font(.system(size: 17))
                    .italic()
                    .foregroundColor(.textTertiary)
            } else {
                Text(voiceViewModel.rawTranscript)
                    .font(.system(size: 17))
                    .foregroundColor(.textPrimary)
                    .lineSpacing(8) // ~1.65 line height at 17px
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Cursor indicator when recording
                if voiceViewModel.isRecording {
                    Rectangle()
                        .fill(journalColor)
                        .frame(width: 2, height: 20)
                        .opacity(cursorOpacity)
                        .onAppear {
                            withAnimation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true)) {
                                cursorOpacity = 0.0
                            }
                        }
                }
            }
        }
    }

    // MARK: - Controls

    private var controlsSection: some View {
        HStack(spacing: Spacing.lg) {
            // Cancel button
            Button(action: onCancel) {
                Text("Discard")
                    .font(.body)
                    .foregroundColor(.textSecondary)
            }

            Spacer()

            if voiceViewModel.isRecording {
                // Stop recording button
                Button {
                    Task {
                        await voiceViewModel.stopRecording()
                    }
                } label: {
                    Image(systemName: "stop.circle.fill")
                        .font(.system(size: 44))
                        .foregroundColor(journalColor)
                }
            } else {
                // Submit button (after stopping)
                Button {
                    let transcript = voiceViewModel.rawTranscript
                    let duration = voiceViewModel.recordingDuration
                    onSubmit(transcript, duration)
                } label: {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 24))
                        Text("Submit")
                            .font(.body.weight(.semibold))
                    }
                    .foregroundColor(.textInverse)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.md)
                    .background(journalColor)
                    .cornerRadius(CornerRadius.button)
                }
                .disabled(voiceViewModel.rawTranscript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
        .background(Color.bgBase.opacity(0.5))
    }

    // MARK: - Helpers

    private func formatDuration(_ duration: TimeInterval) -> String {
        let minutes = Int(duration) / 60
        let seconds = Int(duration) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}
