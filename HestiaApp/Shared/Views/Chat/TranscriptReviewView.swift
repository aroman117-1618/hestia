import SwiftUI
import HestiaShared

/// View for reviewing and editing a voice transcript before sending.
///
/// Shows flagged words with highlights and suggestion chips.
/// User can edit the transcript directly or tap suggestions to apply corrections.
struct TranscriptReviewView: View {
    @ObservedObject var viewModel: VoiceInputViewModel
    let onAccept: (String) -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationView {
            ZStack {
                Color.black.opacity(0.95)
                    .ignoresSafeArea()

                VStack(spacing: Spacing.lg) {
                    // Confidence badge
                    confidenceBadge

                    // Editable transcript
                    VStack(alignment: .leading, spacing: Spacing.sm) {
                        Text("Transcript")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))

                        TextEditor(text: $viewModel.editableTranscript)
                            .font(.body)
                            .foregroundColor(.white)
                            .frame(minHeight: 120, maxHeight: 200)
                            .padding(Spacing.sm)
                            .background(Color.white.opacity(0.1))
                            .cornerRadius(CornerRadius.small)
                            .scrollContentBackground(.hidden)
                    }

                    // Flagged words section
                    if !viewModel.flaggedWords.isEmpty {
                        flaggedWordsSection
                    }

                    Spacer()

                    // Action buttons
                    VStack(spacing: Spacing.sm) {
                        Button {
                            let transcript = viewModel.acceptTranscript()
                            onAccept(transcript)
                        } label: {
                            Text("Send to Chat")
                                .font(.body.weight(.semibold))
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(Spacing.md)
                                .background(Color.healthyGreen)
                                .cornerRadius(CornerRadius.button)
                        }

                        Button {
                            onCancel()
                        } label: {
                            Text("Discard")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.6))
                                .frame(maxWidth: .infinity)
                                .padding(Spacing.md)
                        }
                    }
                }
                .padding(Spacing.lg)
            }
            .navigationTitle("Review Transcript")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        onCancel()
                    }
                    .foregroundColor(.white)
                }
            }
        }
    }

    // MARK: - Confidence Badge

    private var confidenceBadge: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: confidenceIcon)
                .foregroundColor(confidenceColor)

            Text("Confidence: \(Int(viewModel.overallConfidence * 100))%")
                .font(.subheadline.weight(.medium))
                .foregroundColor(confidenceColor)

            if viewModel.needsReview {
                Text("Review suggested")
                    .font(.caption)
                    .foregroundColor(.warningYellow)
                    .padding(.horizontal, Spacing.xs)
                    .padding(.vertical, 2)
                    .background(Color.warningYellow.opacity(0.2))
                    .cornerRadius(4)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var confidenceIcon: String {
        if viewModel.overallConfidence >= 0.8 {
            return "checkmark.circle.fill"
        } else if viewModel.overallConfidence >= 0.5 {
            return "exclamationmark.triangle.fill"
        } else {
            return "xmark.circle.fill"
        }
    }

    private var confidenceColor: Color {
        if viewModel.overallConfidence >= 0.8 {
            return .healthyGreen
        } else if viewModel.overallConfidence >= 0.5 {
            return .warningYellow
        } else {
            return .errorRed
        }
    }

    // MARK: - Flagged Words

    private var flaggedWordsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Possible Issues (\(viewModel.flaggedWords.count))")
                .font(.caption)
                .foregroundColor(.white.opacity(0.6))

            ForEach(viewModel.flaggedWords, id: \.uniqueKey) { flagged in
                FlaggedWordCard(
                    flaggedWord: flagged,
                    onApplySuggestion: { suggestion in
                        viewModel.applySuggestion(for: flagged, suggestion: suggestion)
                    }
                )
            }
        }
    }
}

// MARK: - Flagged Word Card

struct FlaggedWordCard: View {
    let flaggedWord: VoiceFlaggedWordResponse
    let onApplySuggestion: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            HStack {
                // Flagged word
                Text("\"\(flaggedWord.word)\"")
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.warningYellow)

                Spacer()

                // Reason badge
                if !flaggedWord.reason.isEmpty {
                    Text(flaggedWord.reason)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.white.opacity(0.1))
                        .cornerRadius(4)
                }
            }

            // Suggestion chips
            if !flaggedWord.suggestions.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Spacing.xs) {
                        ForEach(flaggedWord.suggestions, id: \.self) { suggestion in
                            Button {
                                onApplySuggestion(suggestion)
                            } label: {
                                Text(suggestion)
                                    .font(.caption.weight(.medium))
                                    .foregroundColor(.healthyGreen)
                                    .padding(.horizontal, Spacing.sm)
                                    .padding(.vertical, 4)
                                    .background(Color.healthyGreen.opacity(0.2))
                                    .cornerRadius(CornerRadius.small)
                            }
                        }
                    }
                }
            }
        }
        .padding(Spacing.sm)
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.small)
    }
}
