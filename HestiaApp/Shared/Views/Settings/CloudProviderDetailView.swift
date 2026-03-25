import SwiftUI
import HestiaShared

/// Detail view for a single cloud provider — state, model, health, usage, removal
struct CloudProviderDetailView: View {
    let provider: CloudProvider
    @ObservedObject var viewModel: CloudSettingsViewModel
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var selectedState: CloudProvider.ProviderState
    @State private var selectedModel: String
    @State private var showingRemoveConfirmation = false

    init(provider: CloudProvider, viewModel: CloudSettingsViewModel) {
        self.provider = provider
        self.viewModel = viewModel
        _selectedState = State(initialValue: provider.state)
        _selectedModel = State(initialValue: provider.activeModelId ?? "")
    }

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    // Provider header
                    providerHeader

                    // Routing state
                    routingStateSection

                    // Model selection
                    modelSection

                    // API key status
                    apiKeySection

                    // Health check
                    healthSection

                    // Danger zone
                    dangerZone

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(provider.provider.displayName)
        .navigationBarTitleDisplayMode(.large)
        .alert("Remove Provider?", isPresented: $showingRemoveConfirmation) {
            Button("Remove", role: .destructive) {
                Task {
                    let success = await viewModel.removeProvider(provider)
                    if success {
                        dismiss()
                    }
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove \(provider.provider.displayName) and delete its API key from Keychain. Cloud routing state will be recalculated.")
        }
    }

    // MARK: - Provider Header

    private var providerHeader: some View {
        VStack(spacing: Spacing.md) {
            Image(systemName: provider.provider.iconName)
                .font(.system(size: 48))
                .foregroundColor(provider.provider.color)

            Text(provider.provider.displayName)
                .foregroundColor(.textPrimary)
                .font(.title2)
                .fontWeight(.bold)

            HStack(spacing: Spacing.sm) {
                Text(provider.state.displayName)
                    .font(.caption)
                    .foregroundColor(provider.state.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(provider.state.color.opacity(0.15))
                    .cornerRadius(6)

                if provider.isHealthy {
                    Label("Healthy", systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundColor(.healthyGreen)
                } else {
                    Label(provider.healthStatus.capitalized, systemImage: "exclamationmark.circle")
                        .font(.caption)
                        .foregroundColor(.warningYellow)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.lg)
    }

    // MARK: - Routing State

    private var routingStateSection: some View {
        sectionWrapper("Routing State") {
            VStack(spacing: Spacing.sm) {
                ForEach(CloudProvider.ProviderState.allCases) { state in
                    Button {
                        selectedState = state
                        Task {
                            await viewModel.updateState(provider, newState: state)
                        }
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(state.displayName)
                                    .foregroundColor(.textPrimary)

                                Text(state.description)
                                    .font(.caption)
                                    .foregroundColor(.textSecondary)
                            }

                            Spacer()

                            if selectedState == state {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(state.color)
                            } else {
                                Image(systemName: "circle")
                                    .foregroundColor(.textTertiary)
                            }
                        }
                    }
                    .settingsRow()
                }
            }
        }
    }

    // MARK: - Model Selection

    private var modelSection: some View {
        sectionWrapper("Active Model") {
            VStack(spacing: Spacing.sm) {
                if provider.availableModels.isEmpty {
                    HStack {
                        Text("No models detected")
                            .foregroundColor(.textSecondary)
                        Spacer()
                    }
                    .settingsRow()
                } else {
                    ForEach(provider.availableModels, id: \.self) { modelId in
                        Button {
                            selectedModel = modelId
                            Task {
                                await viewModel.updateModel(provider, modelId: modelId)
                            }
                        } label: {
                            HStack {
                                Text(modelId)
                                    .foregroundColor(.textPrimary)
                                    .font(.system(.body, design: .monospaced))
                                    .lineLimit(1)

                                Spacer()

                                if selectedModel == modelId || (selectedModel.isEmpty && modelId == provider.activeModelId) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundColor(.healthyGreen)
                                } else {
                                    Image(systemName: "circle")
                                        .foregroundColor(.textTertiary)
                                }
                            }
                        }
                        .settingsRow()
                    }
                }
            }
        }
    }

    // MARK: - API Key Status

    private var apiKeySection: some View {
        sectionWrapper("API Key") {
            HStack {
                Image(systemName: provider.hasApiKey ? "key.fill" : "key")
                    .foregroundColor(provider.hasApiKey ? .healthyGreen : .errorRed)

                Text(provider.hasApiKey ? "Configured (stored in Keychain)" : "Not configured")
                    .foregroundColor(.textPrimary)

                Spacer()

                if provider.hasApiKey {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.healthyGreen)
                }
            }
            .settingsRow()
        }
    }

    // MARK: - Health Check

    private var healthSection: some View {
        sectionWrapper("Health") {
            VStack(spacing: Spacing.sm) {
                // Last check info
                if let lastCheck = provider.lastHealthCheck {
                    HStack {
                        Text("Last Check")
                            .foregroundColor(.white.opacity(0.7))
                        Spacer()
                        Text(lastCheck, style: .relative)
                            .foregroundColor(.textSecondary)
                    }
                    .settingsRow()
                }

                // Health check result
                if let result = viewModel.healthCheckResult {
                    HStack {
                        Text("Result")
                            .foregroundColor(.white.opacity(0.7))
                        Spacer()
                        Text(result)
                            .foregroundColor(result == "Healthy" ? .healthyGreen : .warningYellow)
                    }
                    .settingsRow()
                }

                // Check button
                Button {
                    Task {
                        await viewModel.checkHealth(provider)
                    }
                } label: {
                    HStack {
                        if viewModel.isCheckingHealth {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Image(systemName: "heart.text.square")
                        }
                        Text(viewModel.isCheckingHealth ? "Checking..." : "Run Health Check")
                        Spacer()
                    }
                    .foregroundColor(.textPrimary)
                }
                .settingsRow()
                .disabled(viewModel.isCheckingHealth)
            }
        }
    }

    // MARK: - Danger Zone

    private var dangerZone: some View {
        sectionWrapper("Danger Zone") {
            Button {
                showingRemoveConfirmation = true
            } label: {
                HStack {
                    Image(systemName: "trash")
                    Text("Remove Provider")
                    Spacer()
                }
                .foregroundColor(.errorRed)
            }
            .settingsRow()
        }
    }

    // MARK: - Section Wrapper

    private func sectionWrapper<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text(title)
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                content()
            }
            .padding(.horizontal, Spacing.lg)
        }
    }
}
