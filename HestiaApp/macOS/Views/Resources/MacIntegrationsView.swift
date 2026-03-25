import SwiftUI
import HestiaShared

struct MacIntegrationsView: View {
    @StateObject private var viewModel = MacIntegrationsViewModel()
    @State private var expandedIntegration: IntegrationType?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: MacSpacing.md) {
                ForEach(viewModel.integrations) { integration in
                    integrationCard(integration)
                }
            }
            .padding(MacSpacing.xl)
        }
        .onAppear {
            viewModel.setup()
        }
    }

    // MARK: - Integration Card

    private func integrationCard(_ integration: Integration) -> some View {
        VStack(spacing: 0) {
            // Header row
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if expandedIntegration == integration.id {
                        expandedIntegration = nil
                    } else {
                        expandedIntegration = integration.id
                    }
                }
            } label: {
                HStack(spacing: MacSpacing.md) {
                    Image(systemName: integration.iconName)
                        .font(MacTypography.pageTitle)
                        .foregroundStyle(MacColors.amberAccent)
                        .frame(width: 28, height: 28)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(integration.name)
                            .font(MacTypography.bodyMedium)
                            .foregroundStyle(MacColors.textPrimary)

                        Text("\(integration.toolCount) tools")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                    }

                    Spacer()

                    // Status badge
                    HStack(spacing: 4) {
                        Circle()
                            .fill(integration.status.color)
                            .frame(width: 6, height: 6)
                        Text(integration.status.displayName)
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    Image(systemName: expandedIntegration == integration.id ? "chevron.up" : "chevron.down")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                }
                .padding(MacSpacing.lg)
            }
            .buttonStyle(.hestia)

            // Expanded detail
            if expandedIntegration == integration.id {
                MacColors.divider.frame(height: 1)
                    .padding(.horizontal, MacSpacing.md)

                VStack(alignment: .leading, spacing: MacSpacing.md) {
                    // Permission action
                    if integration.requiresDevicePermission && integration.status == .notConnected {
                        Button {
                            Task { await viewModel.requestPermission(for: integration.id) }
                        } label: {
                            HStack(spacing: MacSpacing.xs) {
                                Image(systemName: "lock.open")
                                Text("Grant Permission")
                            }
                            .font(MacTypography.smallMedium)
                            .foregroundStyle(MacColors.amberAccent)
                            .padding(.horizontal, MacSpacing.md)
                            .padding(.vertical, 6)
                            .background(MacColors.activeTabBackground)
                            .cornerRadius(MacCornerRadius.treeItem)
                        }
                        .buttonStyle(.hestia)
                    }

                    if integration.status == .denied {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundStyle(MacColors.healthRed)
                            Text("Permission denied. Open System Settings to grant access.")
                                .font(MacTypography.caption)
                                .foregroundStyle(MacColors.textSecondary)
                        }
                    }

                    // Tools list
                    Text("Available Tools")
                        .font(MacTypography.sectionLabel)
                        .foregroundStyle(MacColors.textSecondary)
                        .textCase(.uppercase)

                    ForEach(integration.tools) { tool in
                        toolRow(tool)
                    }
                }
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)
            }
        }
        .background(MacColors.panelBackground)
        .cornerRadius(MacCornerRadius.panel)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
    }

    // MARK: - Tool Row

    private func toolRow(_ tool: IntegrationTool) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: tool.requiresApproval ? "checkmark.shield" : "terminal")
                .font(MacTypography.caption)
                .foregroundStyle(tool.requiresApproval ? MacColors.healthAmber : MacColors.textFaint)
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 1) {
                Text(tool.name)
                    .font(MacTypography.smallMedium)
                    .foregroundStyle(MacColors.textPrimary)

                Text(tool.description)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                    .lineLimit(1)
            }

            Spacer()

            if tool.requiresApproval {
                Text("Approval")
                    .font(MacTypography.micro)
                    .foregroundStyle(MacColors.healthAmber)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(MacColors.healthAmberBg)
                    .cornerRadius(4)
            }
        }
        .padding(.vertical, 2)
    }
}
