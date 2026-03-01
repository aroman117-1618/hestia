import SwiftUI
import HestiaShared

struct MacMessageInputBar: View {
    @Binding var messageText: String
    @EnvironmentObject var appState: AppState
    @FocusState private var isInputFocused: Bool
    @State private var showCommandPicker = false
    let onSend: () -> Void

    var body: some View {
        HStack(spacing: MacSpacing.sm) {
            // Commands
            Button { showCommandPicker.toggle() } label: {
                Image(systemName: "terminal")
                    .font(.system(size: 15))
                    .foregroundStyle(showCommandPicker ? MacColors.amberAccent : MacColors.textSecondary)
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.plain)
            .popover(isPresented: $showCommandPicker, arrowEdge: .top) {
                CommandPickerView { command in
                    messageText = command
                    showCommandPicker = false
                    isInputFocused = true
                }
            }

            // Text field
            TextField("Message \(appState.currentMode.displayName)...", text: $messageText)
                .font(MacTypography.inputField)
                .textFieldStyle(.plain)
                .foregroundStyle(MacColors.textPrimary)
                .focused($isInputFocused)
                .onSubmit(onSend)

            // Mic
            Button {} label: {
                Image(systemName: "mic")
                    .font(.system(size: 15))
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.plain)

            // Send button
            Button(action: onSend) {
                Image(systemName: "paperplane.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.buttonTextDark)
                    .frame(width: MacSize.sendButtonSize, height: MacSize.sendButtonSize)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.sendButton))
            }
            .buttonStyle(.plain)
            .disabled(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .opacity(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.5 : 1)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .contentShape(Capsule())
        .onTapGesture { isInputFocused = true }
        .clipShape(Capsule())
        .padding(.horizontal, 33)
        .padding(.vertical, MacSpacing.lg)
        .background(MacColors.chatInputBackground)
    }
}
