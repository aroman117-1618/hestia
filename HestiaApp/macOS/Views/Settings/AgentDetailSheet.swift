import SwiftUI
import HestiaShared

struct AgentDetailSheet: View {
    let agent: AgentConfigInfo
    @ObservedObject var vm: MacAgentsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab: AgentDetailTab = .identity

    enum AgentDetailTab: String, CaseIterable {
        case identity = "Identity"
        case personality = "Personality"
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            sheetHeader

            // Tab picker
            tabPicker

            // Tab content
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
        .frame(width: 520, height: 580)
        .background(MacColors.windowBackground)
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

    // MARK: - Identity Tab

    private var identityTab: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            identityField("Name", value: agent.name, icon: "person")
            identityField("Full Name", value: agent.identity.fullName, icon: "person.text.rectangle")
            identityField("Vibe", value: agent.identity.vibe, icon: "sparkles")

            HStack(spacing: MacSpacing.lg) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Colors")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    HStack(spacing: MacSpacing.sm) {
                        Circle()
                            .fill(Color(hex: agent.identity.gradientColor1))
                            .frame(width: 24, height: 24)
                        Circle()
                            .fill(Color(hex: agent.identity.gradientColor2))
                            .frame(width: 24, height: 24)
                    }
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Temperature")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    Text(String(format: "%.1f", agent.identity.temperature))
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textPrimary)
                }
            }
        }
        .padding(MacSpacing.xl)
    }

    private func identityField(_ label: String, value: String, icon: String) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(MacColors.amberAccent)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                Text(value.isEmpty ? "—" : value)
                    .font(MacTypography.body)
                    .foregroundStyle(value.isEmpty ? MacColors.textFaint : MacColors.textPrimary)
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
                    isEditable: true,
                    onSave: { _ in
                        Task { await vm.savePersonality(for: agent) }
                    }
                )
                .frame(minHeight: 350)
                .onChange(of: vm.personalityContent) { _, _ in
                    // Auto-save after 2s
                    Task {
                        try? await Task.sleep(for: .seconds(2))
                        await vm.savePersonality(for: agent)
                    }
                }
            }
        }
        .padding(MacSpacing.xl)
    }
}
