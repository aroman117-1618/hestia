import SwiftUI
import HestiaShared

struct MacAddCloudProviderView: View {
    @ObservedObject var viewModel: MacCloudSettingsViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var selectedType: CloudProvider.ProviderType = .anthropic
    @State private var apiKey = ""
    @State private var selectedState: CloudProvider.ProviderState = .enabledSmart

    var body: some View {
        VStack(spacing: MacSpacing.xl) {
            // Title
            Text("Add Cloud Provider")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            // Provider picker
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                Text("Provider")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)

                Picker("", selection: $selectedType) {
                    ForEach(CloudProvider.ProviderType.allCases) { type in
                        Text(type.displayName).tag(type)
                    }
                }
                .pickerStyle(.segmented)
            }

            // API Key
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                Text("API Key")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)

                SecureField("Enter API key...", text: $apiKey)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(MacColors.textPrimary)
                    .padding(MacSpacing.sm)
                    .background(MacColors.searchInputBackground)
                    .cornerRadius(MacCornerRadius.search)
            }

            // State
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                Text("Initial Routing State")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)

                Picker("", selection: $selectedState) {
                    ForEach(CloudProvider.ProviderState.allCases, id: \.self) { state in
                        Text(state.displayName).tag(state)
                    }
                }
                .pickerStyle(.segmented)
            }

            // Error
            if let error = viewModel.error {
                Text(error)
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.healthRed)
            }

            // Actions
            HStack(spacing: MacSpacing.md) {
                Spacer()

                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.plain)
                .foregroundStyle(MacColors.textSecondary)

                Button {
                    Task {
                        let success = await viewModel.addProvider(
                            type: selectedType,
                            apiKey: apiKey,
                            state: selectedState,
                            modelId: nil
                        )
                        if success {
                            dismiss()
                        }
                    }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        if viewModel.isAddingProvider {
                            ProgressView()
                                .controlSize(.small)
                                .tint(.white)
                        }
                        Text("Add Provider")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.plain)
                .disabled(apiKey.count < 10 || viewModel.isAddingProvider)
            }
        }
        .padding(MacSpacing.xxl)
        .frame(width: 420)
        .background(MacColors.panelBackground)
    }
}
