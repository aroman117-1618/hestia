#if os(iOS)
import SwiftUI
import HestiaShared

/// Full-screen overlay for active voice conversations.
/// Shows orb state, live transcript, Hestia's response, and stop button.
struct VoiceConversationOverlay: View {
    @ObservedObject var manager: VoiceConversationManager
    let onStop: () -> Void

    var body: some View {
        ZStack {
            Color.black.opacity(0.95)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                HestiaOrbView(state: orbState, size: 160)
                    .padding(.bottom, Spacing.xl)

                stateLabel
                    .padding(.bottom, Spacing.lg)

                transcriptArea
                    .frame(maxHeight: 200)
                    .padding(.horizontal, Spacing.xl)

                Spacer()

                Button(action: onStop) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.white.opacity(0.6))
                }
                .padding(.bottom, 60)
            }
        }
        .transition(.opacity)
    }

    private var orbState: HestiaOrbState {
        switch manager.state {
        case .idle: return .idle
        case .listening: return .listening
        case .processing: return .thinking
        case .speaking: return .speaking
        }
    }

    private var stateLabel: some View {
        Group {
            switch manager.state {
            case .idle:
                Text("Ready").foregroundColor(.white.opacity(0.4))
            case .listening:
                Text("Listening...").foregroundColor(.white.opacity(0.6))
            case .processing:
                Text("Thinking...").foregroundColor(.white.opacity(0.6))
            case .speaking:
                Text("Speaking").foregroundColor(.white.opacity(0.6))
            }
        }
        .font(.system(size: 15))
    }

    @ViewBuilder
    private var transcriptArea: some View {
        VStack(spacing: Spacing.md) {
            if !manager.currentTranscript.isEmpty {
                Text(manager.currentTranscript)
                    .font(.system(size: 16))
                    .foregroundColor(.white.opacity(0.5))
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
            }

            if !manager.currentResponse.isEmpty && manager.state == .speaking {
                Text(manager.currentResponse)
                    .font(.system(size: 17, weight: .medium))
                    .foregroundColor(.white.opacity(0.9))
                    .multilineTextAlignment(.center)
                    .lineLimit(6)
            }

            if let error = manager.error {
                Text(error)
                    .font(.system(size: 14))
                    .foregroundColor(.red.opacity(0.8))
            }
        }
    }
}
#endif
