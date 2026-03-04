import SwiftUI

/// Compact feedback row shown below AI message bubbles on hover.
/// Allows thumbs-up/down feedback that syncs with the outcomes API.
struct OutcomeFeedbackRow: View {
    let messageId: String
    let currentFeedback: String?
    let onFeedback: (String, String?) -> Void

    @State private var showNoteField: Bool = false
    @State private var feedbackNote: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            HStack(spacing: MacSpacing.sm) {
                // Thumbs up
                Button {
                    if currentFeedback == "positive" {
                        return // Already submitted
                    }
                    onFeedback("positive", nil)
                } label: {
                    Image(systemName: currentFeedback == "positive"
                          ? "hand.thumbsup.fill"
                          : "hand.thumbsup")
                        .font(.system(size: 11))
                        .foregroundStyle(feedbackColor(for: "positive"))
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.hestiaIcon)
                .help("Helpful response")

                // Thumbs down
                Button {
                    if currentFeedback == "negative" {
                        return // Already submitted
                    }
                    showNoteField = true
                    onFeedback("negative", nil)
                } label: {
                    Image(systemName: currentFeedback == "negative"
                          ? "hand.thumbsdown.fill"
                          : "hand.thumbsdown")
                        .font(.system(size: 11))
                        .foregroundStyle(feedbackColor(for: "negative"))
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.hestiaIcon)
                .help("Unhelpful response")
            }

            // Optional note field (appears after thumbs-down)
            if showNoteField && currentFeedback == "negative" {
                HStack(spacing: MacSpacing.xs) {
                    TextField("What went wrong?", text: $feedbackNote)
                        .textFieldStyle(.plain)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textPrimary)
                        .padding(.horizontal, MacSpacing.sm)
                        .padding(.vertical, 4)
                        .background(
                            MacColors.searchInputBackground
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .frame(maxWidth: 200)
                        .onSubmit {
                            submitNote()
                        }

                    Button {
                        submitNote()
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 14))
                            .foregroundStyle(MacColors.amberAccent)
                    }
                    .buttonStyle(.hestiaIcon)
                    .disabled(feedbackNote.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }

    // MARK: - Helpers

    private func feedbackColor(for type: String) -> Color {
        if currentFeedback == type {
            return type == "positive"
                ? Color.green
                : Color.red
        }
        return MacColors.textFaint
    }

    private func submitNote() {
        let trimmed = feedbackNote.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        onFeedback("negative", trimmed)
        showNoteField = false
    }
}
