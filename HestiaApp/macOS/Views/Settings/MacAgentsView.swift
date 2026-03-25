import SwiftUI
import HestiaShared

struct MacAgentsView: View {
    @StateObject private var vm = MacAgentsViewModel()

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            if vm.isLoading && vm.agents.isEmpty {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 150)
            } else if let error = vm.errorMessage {
                VStack(spacing: MacSpacing.md) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(MacTypography.mediumValue)
                        .foregroundStyle(MacColors.statusWarning)
                    Text(error)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                    Button("Retry") {
                        Task { await vm.loadAgents() }
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(MacColors.amberAccent)
                }
                .frame(maxWidth: .infinity, minHeight: 150)
            } else if vm.agents.isEmpty {
                emptyState
            } else {
                agentGrid
            }
        }
        .task {
            await vm.loadAgents()
        }
        .sheet(item: $vm.selectedAgent) { agent in
            AgentDetailSheet(agent: agent, vm: vm)
        }
    }

    // MARK: - Agent Grid

    private var agentGrid: some View {
        LazyVGrid(columns: [
            GridItem(.adaptive(minimum: 200), spacing: MacSpacing.md),
        ], spacing: MacSpacing.md) {
            ForEach(vm.agents) { agent in
                AgentCardView(agent: agent, isDefault: agent.directoryName == vm.defaultAgent) {
                    vm.selectedAgent = agent
                    Task { await vm.loadPersonality(for: agent) }
                }
            }
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "person.3.fill")
                .font(MacTypography.largeValue)
                .foregroundStyle(MacColors.textFaint)
            Text("No agents configured")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 150)
    }
}

// MARK: - Agent Avatar (matches chat panel rendering)

/// Renders an agent avatar using the asset catalog image if available,
/// falling back to a gradient circle with the agent's first initial.
/// Matches the rendering in MacChatPanelView and MacMessageBubble.
struct AgentAvatar: View {
    let agent: AgentConfigInfo
    let size: CGFloat

    /// Map agent directory names to HestiaMode for avatar/gradient lookup
    private var mode: HestiaMode? {
        switch agent.directoryName {
        case "tia": return .tia
        case "mira": return .mira
        case "olly": return .olly
        default: return nil
        }
    }

    var body: some View {
        Group {
            if let mode, let image = mode.avatarImage {
                // Asset catalog image (hestia-profile, artemis-profile, apollo-profile)
                image
                    .resizable()
                    .scaledToFill()
            } else if let mode {
                // Known agent without custom image — use mode gradient
                Circle()
                    .fill(mode.gradient)
                    .overlay {
                        Text(agent.name.prefix(1))
                            .font(.system(size: size * 0.45, weight: .bold))
                            .foregroundStyle(MacColors.textPrimary)
                    }
            } else {
                // Unknown agent — use API gradient colors
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(hex: agent.identity.gradientColor1),
                                Color(hex: agent.identity.gradientColor2)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .overlay {
                        Text(agent.name.prefix(1))
                            .font(.system(size: size * 0.45, weight: .bold))
                            .foregroundStyle(MacColors.textPrimary)
                    }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay {
            Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1)
        }
    }
}

// MARK: - Agent Card

struct AgentCardView: View {
    let agent: AgentConfigInfo
    let isDefault: Bool
    let onTap: () -> Void

    @State private var isHovering = false

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: MacSpacing.md) {
                // Avatar (matches chat panel rendering)
                AgentAvatar(agent: agent, size: 48)

                // Name + vibe
                VStack(spacing: 2) {
                    HStack(spacing: 4) {
                        Text(agent.name)
                            .font(MacTypography.cardTitle)
                            .foregroundStyle(MacColors.textPrimary)

                        if isDefault {
                            Image(systemName: "star.fill")
                                .font(MacTypography.micro)
                                .foregroundStyle(MacColors.amberAccent)
                        }
                    }

                    if !agent.identity.vibe.isEmpty {
                        Text(agent.identity.vibe)
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)
                            .lineLimit(1)
                    }
                }

                // Edit indicator
                Text("Edit")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.amberAccent)
                    .opacity(isHovering ? 1 : 0)
            }
            .padding(MacSpacing.lg)
            .frame(maxWidth: .infinity, minHeight: MacSize.agentCardHeight)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .fill(isHovering ? MacColors.hoverBackground : MacColors.searchInputBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .strokeBorder(isHovering ? MacColors.amberAccent.opacity(0.3) : MacColors.cardBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                isHovering = hovering
            }
        }
        .accessibilityLabel("\(agent.name) agent\(isDefault ? ", default" : "")")
        .accessibilityHint("Click to edit")
    }
}
