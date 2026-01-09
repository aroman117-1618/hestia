import SwiftUI

/// A single message bubble in the chat
struct MessageBubble: View {
    let message: ConversationMessage

    private var isUser: Bool {
        message.role == .user
    }

    /// Check if content looks like raw tool_call JSON (shouldn't display to user)
    private var isRawToolCall: Bool {
        let content = message.content.trimmingCharacters(in: .whitespacesAndNewlines)
        return content.hasPrefix("{") && (content.contains("\"tool_call\"") || content.contains("\"tool\":"))
    }

    /// Cleaned display content - hides raw JSON tool calls
    private var displayContent: String {
        if isRawToolCall {
            return "Working on that..."
        }
        return message.content
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: Spacing.sm) {
            if isUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: Spacing.xs) {
                // Message content
                if isRawToolCall {
                    // Show tool execution indicator instead of raw JSON
                    HStack(spacing: Spacing.sm) {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                        Text("Working on that...")
                            .font(.messageBody)
                            .foregroundColor(.white.opacity(0.8))
                    }
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm + 2)
                    .background(bubbleBackground)
                    .cornerRadius(CornerRadius.standard)
                } else {
                    Text(message.content)
                        .font(.messageBody)
                        .foregroundColor(.white)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.sm + 2)
                        .background(bubbleBackground)
                        .cornerRadius(CornerRadius.standard)
                }

                // Timestamp
                Text(message.timestamp, style: .time)
                    .font(.messageTimestamp)
                    .foregroundColor(.white.opacity(0.5))
                    .padding(.horizontal, Spacing.xs)
            }

            if !isUser {
                Spacer(minLength: 60)
            }
        }
        .padding(.horizontal, Spacing.md)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to copy")
    }

    // MARK: - Styling

    private var bubbleBackground: Color {
        isUser ? Color.userBubbleBackground : Color.assistantBubbleBackground
    }

    private var accessibilityLabel: String {
        let sender = isUser ? "You said" : "\(message.mode?.displayName ?? "Hestia") said"
        return "\(sender): \(message.content)"
    }
}

// MARK: - Preview

struct MessageBubble_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: Spacing.md) {
                MessageBubble(message: ConversationMessage(
                    id: "1",
                    role: .assistant,
                    content: "Hi Boss, ready for some good trouble?",
                    timestamp: Date(),
                    mode: .tia
                ))

                MessageBubble(message: ConversationMessage(
                    id: "2",
                    role: .user,
                    content: "What's on my calendar today?",
                    timestamp: Date(),
                    mode: nil
                ))

                MessageBubble(message: ConversationMessage(
                    id: "3",
                    role: .assistant,
                    content: "You have 3 meetings today. The first one is with Gavin in 12 minutes in Conference Room A.",
                    timestamp: Date(),
                    mode: .tia
                ))
            }
            .padding()
        }
    }
}
