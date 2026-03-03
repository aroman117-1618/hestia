import SwiftUI
import HestiaShared

struct MacAgentsView: View {
    @StateObject private var vm = MacAgentsViewModel()

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            if vm.isLoading && vm.agents.isEmpty {
                ProgressView()
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
            GridItem(.flexible(), spacing: MacSpacing.md),
            GridItem(.flexible(), spacing: MacSpacing.md),
            GridItem(.flexible(), spacing: MacSpacing.md),
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
            Image(systemName: "theatermasks")
                .font(.system(size: 32))
                .foregroundStyle(MacColors.textFaint)
            Text("No agents configured")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 150)
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
                // Avatar circle with gradient
                ZStack {
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
                        .frame(width: 48, height: 48)

                    Text(agent.identity.emoji.isEmpty ? String(agent.name.prefix(1)) : agent.identity.emoji)
                        .font(.system(size: 22))
                }

                // Name + vibe
                VStack(spacing: 2) {
                    HStack(spacing: 4) {
                        Text(agent.name)
                            .font(MacTypography.cardTitle)
                            .foregroundStyle(MacColors.textPrimary)

                        if isDefault {
                            Image(systemName: "star.fill")
                                .font(.system(size: 8))
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
