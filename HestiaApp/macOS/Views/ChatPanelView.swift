import SwiftUI
import HestiaShared

struct ChatPanelView: View {
    @State private var currentMode: HestiaMode = .tia
    @State private var messageText: String = ""

    var body: some View {
        VStack(spacing: 0) {
            // Agent header
            agentHeader

            Divider()

            // Message area
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Hestia Workspace chat coming in Phase 1.0")
                        .font(.subheadline)
                        .foregroundStyle(.tertiary)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                }
                .padding()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(nsColor: .textBackgroundColor).opacity(0.5))

            Divider()

            // Input bar
            inputBar
        }
        .frame(minWidth: 280)
    }

    // MARK: - Agent Header

    private var agentHeader: some View {
        HStack {
            Circle()
                .fill(modeColor)
                .frame(width: 10, height: 10)

            Text(currentMode.displayName)
                .font(.headline)

            Spacer()

            Menu {
                ForEach(HestiaMode.allCases, id: \.self) { mode in
                    Button(mode.displayName) {
                        currentMode = mode
                    }
                }
            } label: {
                Image(systemName: "chevron.down.circle")
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: 8) {
            TextField("Message \(currentMode.displayName)...", text: $messageText)
                .textFieldStyle(.plain)
                .onSubmit {
                    sendMessage()
                }

            Button {
                sendMessage()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 22))
                    .foregroundColor(messageText.isEmpty ? .secondary : .accentColor)
            }
            .buttonStyle(.plain)
            .disabled(messageText.isEmpty)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    // MARK: - Helpers

    private var modeColor: Color {
        switch currentMode {
        case .tia: return .blue
        case .mira: return .purple
        case .olly: return .orange
        }
    }

    private func sendMessage() {
        guard !messageText.isEmpty else { return }
        // Placeholder — actual chat integration in Phase 1.0
        messageText = ""
    }
}
