import SwiftUI
import HestiaShared

/// Displays the current pipeline stage as a faded, pulsing bubble below the last message.
/// Shows stages like "Preparing...", "Thinking...", "Using tools..." from SSE metadata.
struct ThinkingIndicator: View {
    let stage: String

    @State private var isPulsing = false

    /// Map raw SSE stage names to user-friendly labels
    private var displayText: String {
        switch stage.lowercased() {
        case "preparing": return "Preparing..."
        case "thinking", "inference": return "Thinking..."
        case "tool_call", "tools": return "Using tools..."
        case "memory": return "Checking memory..."
        case "routing": return "Routing..."
        default: return "\(stage.capitalized)..."
        }
    }

    var body: some View {
        HStack {
            HStack(spacing: Spacing.sm) {
                // Pulsing dot
                Circle()
                    .fill(Color.white.opacity(0.5))
                    .frame(width: 6, height: 6)
                    .scaleEffect(isPulsing ? 1.3 : 0.8)
                    .animation(
                        .easeInOut(duration: 0.8).repeatForever(autoreverses: true),
                        value: isPulsing
                    )

                Text(displayText)
                    .font(.caption)
                    .italic()
                    .foregroundColor(.white.opacity(0.5))
            }
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.sm)
            .background(Color.assistantBubbleBackground)
            .cornerRadius(CornerRadius.standard)

            Spacer()
        }
        .padding(.horizontal, Spacing.md)
        .onAppear { isPulsing = true }
    }
}
