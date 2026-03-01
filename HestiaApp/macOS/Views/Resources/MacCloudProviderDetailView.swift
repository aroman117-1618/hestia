import SwiftUI
import HestiaShared

struct MacCloudProviderDetailView: View {
    let provider: CloudProvider
    @ObservedObject var viewModel: MacCloudSettingsViewModel
    @State private var showingDeleteAlert = false
    @State private var selectedModel: String = ""

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header
                .padding(MacSpacing.lg)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            ScrollView {
                VStack(alignment: .leading, spacing: MacSpacing.xl) {
                    // Status
                    statusSection

                    // Model selector
                    modelSection

                    // State toggle
                    stateSection

                    // Health check
                    healthSection

                    // Danger zone
                    dangerSection
                }
                .padding(MacSpacing.xl)
            }
        }
        .onAppear {
            selectedModel = provider.activeModelId ?? ""
        }
        .alert("Remove Provider", isPresented: $showingDeleteAlert) {
            Button("Remove", role: .destructive) {
                Task {
                    _ = await viewModel.removeProvider(provider)
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove the \(provider.provider.displayName) provider and its API key.")
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: provider.provider.iconName)
                .font(.system(size: 20))
                .foregroundStyle(MacColors.amberAccent)

            VStack(alignment: .leading, spacing: 2) {
                Text(provider.provider.displayName)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                HStack(spacing: MacSpacing.sm) {
                    Text(provider.state.displayName)
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textSecondary)

                    Circle()
                        .fill(provider.healthStatus == "healthy" ? MacColors.healthGreen : MacColors.healthRed)
                        .frame(width: 6, height: 6)

                    Text(provider.healthStatus.capitalized)
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textFaint)
                }
            }

            Spacer()
        }
    }

    // MARK: - Status

    private var statusSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            sectionLabel("Status")

            HStack(spacing: MacSpacing.xl) {
                infoCard(label: "API Key", value: provider.hasApiKey ? "Configured" : "Missing",
                         color: provider.hasApiKey ? MacColors.healthGreen : MacColors.healthRed)

                infoCard(label: "Health", value: provider.healthStatus.capitalized,
                         color: provider.healthStatus == "healthy" ? MacColors.healthGreen : MacColors.textFaint)

                if let model = provider.activeModelId {
                    infoCard(label: "Model", value: model, color: MacColors.amberAccent)
                }
            }
        }
    }

    private func infoCard(label: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textFaint)
            Text(value)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(color)
        }
        .padding(MacSpacing.sm)
        .background(MacColors.innerPillBackground)
        .cornerRadius(MacCornerRadius.treeItem)
    }

    // MARK: - Model Selector

    private var modelSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            sectionLabel("Active Model")

            if provider.availableModels.isEmpty {
                Text("No models available")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textFaint)
            } else {
                Picker("", selection: $selectedModel) {
                    ForEach(provider.availableModels, id: \.self) { model in
                        Text(model).tag(model)
                    }
                }
                .pickerStyle(.menu)
                .onChange(of: selectedModel) {
                    guard !selectedModel.isEmpty, selectedModel != provider.activeModelId else { return }
                    Task { await viewModel.updateModel(provider, modelId: selectedModel) }
                }
            }
        }
    }

    // MARK: - State Toggle

    private var stateSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            sectionLabel("Routing State")

            HStack(spacing: MacSpacing.sm) {
                ForEach(CloudProvider.ProviderState.allCases, id: \.self) { state in
                    Button {
                        Task { await viewModel.updateState(provider, newState: state) }
                    } label: {
                        Text(state.displayName)
                            .font(.system(size: 11, weight: provider.state == state ? .semibold : .regular))
                            .foregroundStyle(provider.state == state ? MacColors.amberAccent : MacColors.textSecondary)
                            .padding(.horizontal, MacSpacing.sm)
                            .padding(.vertical, 4)
                            .background(
                                provider.state == state
                                    ? MacColors.activeTabBackground
                                    : MacColors.innerPillBackground
                            )
                            .cornerRadius(MacCornerRadius.treeItem)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    // MARK: - Health Check

    private var healthSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            sectionLabel("Health Check")

            HStack(spacing: MacSpacing.md) {
                Button {
                    Task { await viewModel.checkHealth(provider) }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        if viewModel.isCheckingHealth {
                            ProgressView()
                                .controlSize(.small)
                                .tint(MacColors.amberAccent)
                        } else {
                            Image(systemName: "heart.text.square")
                        }
                        Text("Run Health Check")
                    }
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, 6)
                    .background(MacColors.activeTabBackground)
                    .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isCheckingHealth)

                if let result = viewModel.healthCheckResult {
                    Text(result)
                        .font(.system(size: 12))
                        .foregroundStyle(result.contains("Healthy") ? MacColors.healthGreen : MacColors.healthRed)
                }
            }
        }
    }

    // MARK: - Danger Zone

    private var dangerSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            sectionLabel("Danger Zone")

            Button {
                showingDeleteAlert = true
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "trash")
                    Text("Remove Provider")
                }
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.healthRed)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, 6)
                .background(MacColors.healthRedBg)
                .cornerRadius(MacCornerRadius.treeItem)
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                        .strokeBorder(MacColors.healthRedBorder, lineWidth: 1)
                }
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Helper

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(MacColors.textSecondary)
            .textCase(.uppercase)
    }
}
