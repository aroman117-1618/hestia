import SwiftUI
import HestiaShared

/// Button to move the current chat session to a background order.
/// Shows a confirmation dialog before sending the session to the orders system.
struct BackgroundSessionButton: View {
    let hasMessages: Bool
    let sessionId: String?
    let onMoveToBackground: (String) async -> Void
    let onNewSession: () -> Void

    @State private var showConfirmation: Bool = false
    @State private var isProcessing: Bool = false

    var body: some View {
        Button {
            if hasMessages, sessionId != nil {
                showConfirmation = true
            } else {
                onNewSession()
            }
        } label: {
            Image(systemName: hasMessages
                  ? "arrow.up.forward.square"
                  : "plus")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 28, height: 28)
                .contentShape(Rectangle())
        }
        .buttonStyle(.hestiaIcon)
        .help(hasMessages ? "Move to background" : "New session")
        .disabled(isProcessing)
        .opacity(isProcessing ? 0.5 : 1.0)
        .alert(
            "Move to Background?",
            isPresented: $showConfirmation
        ) {
            Button("Cancel", role: .cancel) {}
            Button("Move") {
                guard let sessionId else { return }
                isProcessing = true
                Task {
                    await onMoveToBackground(sessionId)
                    isProcessing = false
                }
            }
        } message: {
            Text("This conversation will continue as a background order. A new session will start.")
        }
    }
}
