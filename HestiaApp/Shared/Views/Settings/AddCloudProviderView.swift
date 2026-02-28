import SwiftUI
import HestiaShared

/// Sheet for adding a new cloud provider with API key
struct AddCloudProviderView: View {
    @ObservedObject var viewModel: CloudSettingsViewModel
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var selectedProvider: CloudProvider.ProviderType = .anthropic
    @State private var apiKey: String = ""
    @State private var selectedState: CloudProvider.ProviderState = .enabledSmart
    @State private var modelId: String = ""

    /// Providers already configured (prevent duplicates)
    private var configuredProviders: Set<String> {
        Set(viewModel.providers.map { $0.provider.rawValue })
    }

    private var availableProviders: [CloudProvider.ProviderType] {
        CloudProvider.ProviderType.allCases.filter { !configuredProviders.contains($0.rawValue) }
    }

    private var canAdd: Bool {
        !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && apiKey.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
            && !configuredProviders.contains(selectedProvider.rawValue)
    }

    var body: some View {
        NavigationView {
            ZStack {
                GradientBackground(mode: appState.currentMode)

                ScrollView {
                    VStack(spacing: Spacing.lg) {
                        // Provider selection
                        providerSelection

                        // API key input
                        apiKeyInput

                        // State selection
                        stateSelection

                        // Optional model override
                        modelOverride

                        // Add button
                        addButton

                        Spacer()
                    }
                    .padding(.top, Spacing.md)
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Add Provider")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
            }
        }
    }

    // MARK: - Provider Selection

    private var providerSelection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Provider")
                .font(.sectionHeader)
                .foregroundColor(.white.opacity(0.6))
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            if availableProviders.isEmpty {
                HStack {
                    Image(systemName: "checkmark.circle")
                        .foregroundColor(.healthyGreen)
                    Text("All providers configured")
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                }
                .settingsRow()
                .padding(.horizontal, Spacing.lg)
            } else {
                VStack(spacing: Spacing.sm) {
                    ForEach(availableProviders) { provider in
                        Button {
                            selectedProvider = provider
                        } label: {
                            HStack(spacing: Spacing.md) {
                                Image(systemName: provider.iconName)
                                    .foregroundColor(provider.color)
                                    .font(.title3)
                                    .frame(width: 32)

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(provider.displayName)
                                        .foregroundColor(.white)

                                    Text(providerSubtitle(provider))
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.6))
                                }

                                Spacer()

                                if selectedProvider == provider {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundColor(provider.color)
                                } else {
                                    Image(systemName: "circle")
                                        .foregroundColor(.white.opacity(0.3))
                                }
                            }
                        }
                        .settingsRow()
                    }
                }
                .padding(.horizontal, Spacing.lg)
            }
        }
    }

    private func providerSubtitle(_ provider: CloudProvider.ProviderType) -> String {
        switch provider {
        case .anthropic: return "Claude models"
        case .openai: return "GPT models"
        case .google: return "Gemini models"
        }
    }

    // MARK: - API Key Input

    private var apiKeyInput: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("API Key")
                .font(.sectionHeader)
                .foregroundColor(.white.opacity(0.6))
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                SecureField("Paste your API key", text: $apiKey)
                    .textContentType(.password)
                    .foregroundColor(.white)
                    .accentColor(.white)
                    .settingsRow()

                Text("Stored securely in macOS Keychain. Never transmitted in API responses.")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.4))
                    .padding(.horizontal, Spacing.md)
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - State Selection

    private var stateSelection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Routing Mode")
                .font(.sectionHeader)
                .foregroundColor(.white.opacity(0.6))
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                ForEach(CloudProvider.ProviderState.allCases) { state in
                    Button {
                        selectedState = state
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(state.displayName)
                                    .foregroundColor(.white)

                                Text(state.description)
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.6))
                            }

                            Spacer()

                            if selectedState == state {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(state.color)
                            } else {
                                Image(systemName: "circle")
                                    .foregroundColor(.white.opacity(0.3))
                            }
                        }
                    }
                    .settingsRow()
                }
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Model Override

    private var modelOverride: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Model (Optional)")
                .font(.sectionHeader)
                .foregroundColor(.white.opacity(0.6))
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                TextField("Leave blank for provider default", text: $modelId)
                    .foregroundColor(.white)
                    .accentColor(.white)
                    .settingsRow()

                Text("Provider's default model will be used if left empty.")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.4))
                    .padding(.horizontal, Spacing.md)
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Add Button

    private var addButton: some View {
        Button {
            Task {
                let trimmedModel = modelId.trimmingCharacters(in: .whitespacesAndNewlines)
                let success = await viewModel.addProvider(
                    type: selectedProvider,
                    apiKey: apiKey.trimmingCharacters(in: .whitespacesAndNewlines),
                    state: selectedState,
                    modelId: trimmedModel.isEmpty ? nil : trimmedModel
                )
                if success {
                    dismiss()
                }
            }
        } label: {
            HStack {
                if viewModel.isAddingProvider {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                } else {
                    Image(systemName: "plus.circle.fill")
                }
                Text(viewModel.isAddingProvider ? "Adding..." : "Add \(selectedProvider.displayName)")
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(Spacing.md)
            .background(canAdd ? Color.white.opacity(0.15) : Color.white.opacity(0.05))
            .cornerRadius(CornerRadius.small)
        }
        .disabled(!canAdd || viewModel.isAddingProvider)
        .padding(.horizontal, Spacing.lg)
    }
}
