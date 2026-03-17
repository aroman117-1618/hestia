import SwiftUI
import HestiaShared

struct MacMessageBubble: View {
    let message: ConversationMessage
    let reactions: Set<String>
    let onReaction: (String) -> Void
    let feedbackState: String?
    let onFeedback: (String, String, String?) -> Void

    @State private var isHovered: Bool = false

    private var isUser: Bool { message.role == .user }

    var body: some View {
        if isUser {
            userBubble
        } else {
            aiBubble
        }
    }

    // MARK: - User Bubble (right-aligned, amber)

    private var userBubble: some View {
        HStack(spacing: MacSpacing.lg) {
            Spacer(minLength: 96)
            Text(message.content)
                .font(MacTypography.chatMessage)
                .foregroundStyle(
                    message.content.count < 30
                        ? MacColors.userBubbleTextShort
                        : MacColors.userBubbleText
                )
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.amberAccent)
                .clipShape(UnevenRoundedRectangle(
                    topLeadingRadius: MacCornerRadius.chatBubble,
                    bottomLeadingRadius: MacCornerRadius.chatBubble,
                    bottomTrailingRadius: 0,
                    topTrailingRadius: MacCornerRadius.chatBubble
                ))

            // User avatar
            Circle()
                .fill(Color.gray.opacity(0.3))
                .frame(width: MacSize.chatAvatarSize, height: MacSize.chatAvatarSize)
                .overlay {
                    Image(systemName: "person.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textSecondary)
                }
        }
        .padding(.vertical, MacSpacing.lg)
    }

    // MARK: - AI Bubble (left-aligned, translucent)

    private var aiBubble: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Reasoning steps (collapsible, above message content)
            if let steps = message.reasoningSteps, !steps.isEmpty {
                ReasoningStepsSection(steps: steps)
                    .padding(.leading, MacSpacing.sm)
            }

            // Message bubble with markdown rendering
            MarkdownMessageView(content: message.content)
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.aiBubbleBackground)
                .clipShape(UnevenRoundedRectangle(
                    topLeadingRadius: MacCornerRadius.chatBubble,
                    bottomLeadingRadius: 0,
                    bottomTrailingRadius: MacCornerRadius.chatBubble,
                    topTrailingRadius: MacCornerRadius.chatBubble
                ))

            // Sender label + reactions on same row
            HStack(spacing: MacSpacing.sm) {
                Text(message.mode?.displayName ?? "Tia")
                    .font(MacTypography.senderLabel)
                    .foregroundStyle(MacColors.textSender)

                MacReactionsRow(
                    messageId: message.id,
                    activeReactions: reactions,
                    onReaction: onReaction
                )
            }
            .padding(.leading, MacSpacing.sm)

            // Agent bylines (when specialists contributed)
            if let bylines = message.bylines, !bylines.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(bylines, id: \.agent) { byline in
                        Text(byline.formatted)
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)
                    }
                }
                .padding(.leading, MacSpacing.sm)
            }

            // Outcome feedback (visible on hover or when feedback already submitted)
            if isHovered || feedbackState != nil {
                OutcomeFeedbackRow(
                    messageId: message.id,
                    currentFeedback: feedbackState,
                    onFeedback: { feedback, note in
                        onFeedback(message.id, feedback, note)
                    }
                )
                .padding(.leading, MacSpacing.sm)
                .transition(.opacity)
            }
        }
        .padding(.top, MacSpacing.sm)
        .padding(.bottom, MacSpacing.lg)
        .padding(.trailing, 96)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
    }
}
