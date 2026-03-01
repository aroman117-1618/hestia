import SwiftUI
import HestiaShared

struct MacMessageBubble: View {
    let message: ConversationMessage
    let reactions: Set<String>
    let onReaction: (String) -> Void

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

    // MARK: - Agent Avatar

    private func agentAvatar(for mode: HestiaMode, size: CGFloat) -> some View {
        Group {
            if let image = mode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
            } else {
                Circle()
                    .fill(MacColors.aiAvatarBackground)
                    .overlay {
                        Text(mode.displayName.prefix(1))
                            .font(.system(size: size * 0.45, weight: .bold))
                            .foregroundStyle(MacColors.amberAccent)
                    }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay {
            Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1)
        }
    }

    // MARK: - AI Bubble (left-aligned, translucent)

    private var aiBubble: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(alignment: .bottom, spacing: MacSpacing.lg) {
                // AI avatar
                agentAvatar(for: message.mode ?? .tia, size: MacSize.chatAvatarSize)

                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    // Sender label
                    Text(message.mode?.displayName ?? "Tia")
                        .font(MacTypography.senderLabel)
                        .foregroundStyle(MacColors.textSender)
                        .padding(.horizontal, MacSpacing.sm)

                    // Message bubble
                    Text(message.content)
                        .font(MacTypography.chatMessage)
                        .foregroundStyle(MacColors.textPrimary)
                        .padding(.horizontal, MacSpacing.lg)
                        .padding(.vertical, MacSpacing.md)
                        .background(MacColors.aiBubbleBackground)
                        .clipShape(UnevenRoundedRectangle(
                            topLeadingRadius: MacCornerRadius.chatBubble,
                            bottomLeadingRadius: 0,
                            bottomTrailingRadius: MacCornerRadius.chatBubble,
                            topTrailingRadius: MacCornerRadius.chatBubble
                        ))
                }
            }

            // Reactions row
            MacReactionsRow(
                messageId: message.id,
                activeReactions: reactions,
                onReaction: onReaction
            )
            .padding(.leading, 48)
        }
        .padding(.top, MacSpacing.sm)
        .padding(.bottom, MacSpacing.lg)
        .padding(.trailing, 96)
    }
}
