import SwiftUI
import HestiaShared

struct AgentDetailSheet: View {
    let agent: AgentConfigInfo
    @ObservedObject var vm: MacAgentsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab: AgentDetailTab = .identity

    // Editable identity fields (initialized from agent)
    @State private var editName: String = ""
    @State private var editFullName: String = ""
    @State private var editVibe: String = ""
    @State private var editColor1: String = ""
    @State private var editColor2: String = ""
    @State private var editTemperature: Double = 0.0

    enum AgentDetailTab: String, CaseIterable {
        case identity = "Identity"
        case personality = "Personality"
    }

    var body: some View {
        VStack(spacing: 0) {
            sheetHeader
            tabPicker

            ScrollView {
                switch selectedTab {
                case .identity:
                    identityTab
                case .personality:
                    personalityTab
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(width: 520, height: 600)
        .background(MacColors.windowBackground)
        .overlay(alignment: .bottom) {
            if let result = vm.saveResult {
                saveToast(result: result)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            withAnimation { vm.saveResult = nil }
                        }
                    }
            }
        }
        .animation(MacAnimation.fastSpring, value: vm.saveResult)
        .onDisappear {
            vm.saveResult = nil
        }
        .onAppear {
            // Initialize editable fields from agent data
            editName = agent.name
            editFullName = agent.identity.fullName
            editVibe = agent.identity.vibe
            editColor1 = agent.identity.gradientColor1
            editColor2 = agent.identity.gradientColor2
            editTemperature = agent.identity.temperature
            Task { await vm.loadAgentPhoto(for: agent) }
        }
    }

    // MARK: - Header

    private var sheetHeader: some View {
        HStack {
            AgentAvatar(agent: agent, size: 36)

            VStack(alignment: .leading, spacing: 2) {
                Text(agent.name)
                    .font(MacTypography.pageTitle)
                    .foregroundStyle(MacColors.textPrimary)
                if !agent.identity.vibe.isEmpty {
                    Text(agent.identity.vibe)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            Spacer()

            if vm.isSaving {
                ProgressView()
                    .controlSize(.small)
            }

            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close")
        }
        .padding(MacSpacing.xl)
        .background(MacColors.panelBackground)
    }

    // MARK: - Tab Picker

    private var tabPicker: some View {
        HStack(spacing: 0) {
            ForEach(AgentDetailTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(MacAnimation.fastSpring) {
                        selectedTab = tab
                    }
                } label: {
                    Text(tab.rawValue)
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(selectedTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, MacSpacing.sm)
                        .overlay(alignment: .bottom) {
                            if selectedTab == tab {
                                Rectangle()
                                    .fill(MacColors.amberAccent)
                                    .frame(height: 2)
                            }
                        }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, MacSpacing.xl)
        .background(MacColors.panelBackground)
        .overlay(alignment: .bottom) {
            MacColors.divider.frame(height: 1)
        }
    }

    // MARK: - Identity Tab (Editable)

    private var identityTab: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Photo
            HStack {
                Spacer()
                ProfilePhotoEditor(
                    currentPhotoData: vm.agentPhotoData,
                    initialLetter: String(editName.prefix(1)).uppercased(),
                    size: 72,
                    onUpload: { data in
                        Task { await vm.uploadAgentPhoto(for: agent, imageData: data) }
                    },
                    onDelete: {
                        Task { await vm.deleteAgentPhoto(for: agent) }
                    }
                )
                Spacer()
            }

            // Fields
            editableField("Name", text: $editName, icon: "person")
            editableField("Full Name", text: $editFullName, icon: "person.text.rectangle")
            editableField("Vibe", text: $editVibe, icon: "sparkles")

            // Colors
            HStack(spacing: MacSpacing.lg) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Primary Color")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    HStack(spacing: MacSpacing.sm) {
                        Circle()
                            .fill(Color(hex: editColor1))
                            .frame(width: 24, height: 24)
                        TextField("#hex", text: $editColor1)
                            .font(MacTypography.code)
                            .foregroundStyle(MacColors.textPrimary)
                            .textFieldStyle(.plain)
                            .frame(width: 80)
                    }
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Secondary Color")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    HStack(spacing: MacSpacing.sm) {
                        Circle()
                            .fill(Color(hex: editColor2))
                            .frame(width: 24, height: 24)
                        TextField("#hex", text: $editColor2)
                            .font(MacTypography.code)
                            .foregroundStyle(MacColors.textPrimary)
                            .textFieldStyle(.plain)
                            .frame(width: 80)
                    }
                }
            }

            // Temperature slider
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("Temperature")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    Spacer()
                    Text(String(format: "%.1f", editTemperature))
                        .font(MacTypography.code)
                        .foregroundStyle(MacColors.amberAccent)
                }
                Slider(value: $editTemperature, in: 0...2, step: 0.1)
                    .tint(MacColors.amberAccent)
            }

            // Save button
            HStack {
                Spacer()
                Button {
                    Task {
                        await vm.saveIdentity(
                            for: agent,
                            name: editName,
                            fullName: editFullName,
                            vibe: editVibe,
                            color1: editColor1,
                            color2: editColor2,
                            temperature: editTemperature
                        )
                    }
                } label: {
                    Text("Save Identity")
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, MacSpacing.xl)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.amberAccent)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
                .disabled(!isIdentityValid)
                .opacity(isIdentityValid ? 1 : 0.5)
                .accessibilityLabel("Save identity changes")
                Spacer()
            }
        }
        .padding(MacSpacing.xl)
    }

    private var isIdentityValid: Bool {
        !editName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func editableField(_ label: String, text: Binding<String>, icon: String) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(MacColors.amberAccent)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                TextField(label, text: text)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textPrimary)
                    .textFieldStyle(.plain)
            }
        }
    }

    // MARK: - Personality Tab

    private var personalityTab: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("ANIMA.md — Personality & behavioral instructions")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)

            if vm.isLoadingPersonality {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 300)
            } else {
                MarkdownEditorView(
                    text: $vm.personalityContent,
                    isEditable: true
                )
                .frame(minHeight: 350)

                HStack {
                    Spacer()
                    Button {
                        Task { await vm.savePersonality(for: agent) }
                    } label: {
                        Text("Save Personality")
                            .font(MacTypography.labelMedium)
                            .foregroundStyle(MacColors.buttonTextDark)
                            .padding(.horizontal, MacSpacing.xl)
                            .padding(.vertical, MacSpacing.sm)
                            .background(MacColors.amberAccent)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Save personality changes")
                    Spacer()
                }
            }
        }
        .padding(MacSpacing.xl)
    }

    // MARK: - Save Toast

    private func saveToast(result: MacAgentsViewModel.SaveResult) -> some View {
        let isSuccess: Bool
        let message: String
        switch result {
        case .success(let msg):
            isSuccess = true
            message = msg
        case .failure(let msg):
            isSuccess = false
            message = msg
        }

        return HStack(spacing: MacSpacing.sm) {
            Image(systemName: isSuccess ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                .foregroundStyle(isSuccess ? MacColors.statusGreen : MacColors.statusCritical)
            Text(message)
                .font(MacTypography.labelMedium)
                .foregroundStyle(MacColors.textPrimary)
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.vertical, MacSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(MacColors.panelBackground)
                .shadow(color: .black.opacity(0.3), radius: 8, y: 4)
        )
        .padding(.bottom, MacSpacing.xl)
    }
}
