import SwiftUI
import HestiaShared

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
        // Don't render empty assistant messages (streaming placeholder not yet populated)
        if !isUser && message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            EmptyView()
        } else {
        HStack(alignment: .bottom, spacing: Spacing.sm) {
            if isUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: Spacing.xs) {
                // Reasoning steps (collapsible, above AI message content)
                if !isUser, let steps = message.reasoningSteps, !steps.isEmpty {
                    ReasoningStepsSection(steps: steps)
                }

                // Message content
                if isRawToolCall {
                    // Show tool execution indicator instead of raw JSON
                    HStack(spacing: Spacing.sm) {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .textPrimary))
                            .scaleEffect(0.8)
                        Text("Working on that...")
                            .font(.messageBody)
                            .foregroundColor(.textPrimary.opacity(0.8))
                    }
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm + 2)
                    .background(bubbleBackground)
                    .cornerRadius(CornerRadius.standard)
                } else {
                    Text(message.content)
                        .font(.messageBody)
                        .foregroundColor(.textPrimary)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.sm + 2)
                        .background(bubbleBackground)
                        .cornerRadius(CornerRadius.standard)
                }

                // Agent bylines (when specialists contributed)
                if !isUser, let bylines = message.bylines, !bylines.isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(bylines, id: \.agent) { byline in
                            Text(byline.formatted)
                                .font(.messageTimestamp)
                                .foregroundColor(.textSecondary)
                        }
                    }
                    .padding(.horizontal, Spacing.xs)
                }

                // Timestamp
                Text(message.timestamp, style: .time)
                    .font(.messageTimestamp)
                    .foregroundColor(.textSecondary)
                    .padding(.horizontal, Spacing.xs)

                // Verification risk indicator (amber dot)
                if !isUser, let risk = message.hallucinationRisk, risk == "tool_bypass" || risk == "low_retrieval" {
                    VerificationRiskDot(risk: risk)
                        .padding(.horizontal, Spacing.xs)
                }
            }

            if !isUser {
                Spacer(minLength: 60)
            }
        }
        .padding(.horizontal, Spacing.md)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to copy")
        } // else (non-empty content)
    }

    // MARK: - Styling

    private var bubbleBackground: Color {
        if isUser, message.inputMode == "voice" {
            // Voice conversation bubble — subtle amber tint
            return Color(hex: "FF9F0A").opacity(0.15)
        }
        return isUser ? Color.userBubbleBackground : Color.assistantBubbleBackground
    }

    private var accessibilityLabel: String {
        let sender = isUser ? "You said" : "\(message.mode?.displayName ?? "Hestia") said"
        var label = "\(sender): \(message.content)"
        if let bylines = message.bylines, !bylines.isEmpty {
            let attribution = bylines.map { "\($0.displayName) \($0.summary)" }.joined(separator: ". ")
            label += ". With contributions from \(attribution)"
        }
        return label
    }
}

// MARK: - Verification Risk Dot

private struct VerificationRiskDot: View {
    let risk: String
    @State private var showPopover = false

    var body: some View {
        Button {
            showPopover = true
        } label: {
            Circle()
                .fill(Color.accent)
                .frame(width: 8, height: 8)
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showPopover) {
            Text(popoverText)
                .font(.caption)
                .foregroundColor(.primary)
                .padding()
                .frame(maxWidth: 260)
        }
        .accessibilityLabel("Response may be unverified. Tap for details.")
        .accessibilityHint("Activate to learn more about this response's verification status")
    }

    private var popoverText: String {
        switch risk {
        case "tool_bypass":
            return "Hestia described your calendar, health, or notes data without looking it up first. Verify with the original source before acting on it."
        case "low_retrieval":
            return "Hestia's memory search returned low-confidence results. This response may not reflect your actual stored data."
        default:
            return "This response may contain unverified information. Treat with caution."
        }
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
