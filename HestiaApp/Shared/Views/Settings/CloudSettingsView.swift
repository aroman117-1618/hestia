import SwiftUI
import HestiaShared

/// Cloud provider management — lists configured providers and overall cloud state
struct CloudSettingsView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = CloudSettingsViewModel()

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    // Cloud state summary
                    cloudStateSummary

                    // Provider list or empty state
                    if viewModel.hasProviders {
                        providerList
                    } else {
                        emptyState
                    }

                    // Usage summary (if providers exist)
                    if viewModel.hasProviders {
                        usageSummary
                    }

                    // Add provider button
                    addProviderButton

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Cloud Providers")
        .navigationBarTitleDisplayMode(.large)
        .sheet(isPresented: $viewModel.showingAddProvider) {
            AddCloudProviderView(viewModel: viewModel)
                .environmentObject(appState)
        }
        .onAppear {
            Task {
                await viewModel.refresh()
                await viewModel.loadUsage()
            }
        }
        .alert("Error", isPresented: .constant(viewModel.error != nil)) {
            Button("OK") { viewModel.error = nil }
        } message: {
            Text(viewModel.error ?? "")
        }
    }

    // MARK: - Cloud State Summary

    private var cloudStateSummary: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Cloud Routing")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Effective State")
                        .foregroundColor(.white.opacity(0.7))
                        .font(.caption)

                    Text(viewModel.effectiveStateDisplay)
                        .foregroundColor(.textPrimary)
                        .font(.headline)
                }

                Spacer()

                Circle()
                    .fill(viewModel.effectiveStateColor)
                    .frame(width: 12, height: 12)

                if viewModel.isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                }
            }
            .settingsRow()
            .padding(.horizontal, Spacing.lg)

            Text(cloudStateExplanation)
                .font(.caption)
                .foregroundColor(.textTertiary)
                .padding(.horizontal, Spacing.lg)
        }
    }

    private var cloudStateExplanation: String {
        switch viewModel.effectiveCloudState {
        case "enabled_full":
            return "All queries are routed to the cloud provider. Local models serve as fallback."
        case "enabled_smart":
            return "Queries go to local models first. Cloud is used for failures or large requests."
        default:
            return "All queries use local models only. Add a cloud provider to enable hybrid mode."
        }
    }

    // MARK: - Provider List

    private var providerList: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Providers")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                ForEach(viewModel.providers) { provider in
                    NavigationLink(destination: CloudProviderDetailView(provider: provider, viewModel: viewModel)) {
                        providerRow(provider)
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func providerRow(_ provider: CloudProvider) -> some View {
        HStack(spacing: Spacing.md) {
            // Provider icon
            Image(systemName: provider.provider.iconName)
                .foregroundColor(provider.provider.color)
                .font(.title3)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(provider.provider.displayName)
                        .foregroundColor(.textPrimary)

                    Text(provider.state.displayName)
                        .font(.caption2)
                        .foregroundColor(provider.state.color)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(provider.state.color.opacity(0.15))
                        .cornerRadius(4)
                }

                Text(provider.activeModelId ?? "Default model")
                    .font(.caption)
                    .foregroundColor(.textSecondary)
            }

            Spacer()

            // Health indicator
            Circle()
                .fill(provider.isHealthy ? Color.healthyGreen : Color.white.opacity(0.3))
                .frame(width: 8, height: 8)

            Image(systemName: "chevron.right")
                .foregroundColor(.textSecondary)
        }
        .settingsRow()
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.md) {
            Image(systemName: "cloud")
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            Text("No Cloud Providers")
                .foregroundColor(.textPrimary)
                .font(.headline)

            Text("Add a cloud provider to enable hybrid inference.\nLocal models will be used as fallback.")
                .font(.caption)
                .foregroundColor(.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xl)
    }

    // MARK: - Usage Summary

    private var usageSummary: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Usage (30 days)")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            if let usage = viewModel.usage {
                VStack(spacing: Spacing.sm) {
                    usageRow("Requests", "\(usage.totalRequests)")
                    usageRow("Tokens In", formatTokens(usage.totalTokensIn))
                    usageRow("Tokens Out", formatTokens(usage.totalTokensOut))
                    usageRow("Cost", String(format: "$%.4f", usage.totalCostUsd))
                }
                .padding(.horizontal, Spacing.lg)
            } else if viewModel.isLoadingUsage {
                HStack {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    Text("Loading usage...")
                        .foregroundColor(.textSecondary)
                    Spacer()
                }
                .settingsRow()
                .padding(.horizontal, Spacing.lg)
            }
        }
    }

    private func usageRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .foregroundColor(.white.opacity(0.7))
            Spacer()
            Text(value)
                .foregroundColor(.textPrimary)
                .font(.system(.body, design: .monospaced))
        }
        .settingsRow()
    }

    private func formatTokens(_ count: Int) -> String {
        if count >= 1_000_000 {
            return String(format: "%.1fM", Double(count) / 1_000_000)
        } else if count >= 1_000 {
            return String(format: "%.1fK", Double(count) / 1_000)
        }
        return "\(count)"
    }

    // MARK: - Add Provider Button

    private var addProviderButton: some View {
        Button {
            viewModel.showingAddProvider = true
        } label: {
            HStack {
                Image(systemName: "plus.circle.fill")
                Text("Add Cloud Provider")
            }
            .foregroundColor(.textPrimary)
            .frame(maxWidth: .infinity)
            .padding(Spacing.md)
            .background(Color.white.opacity(0.1))
            .cornerRadius(CornerRadius.small)
        }
        .padding(.horizontal, Spacing.lg)
    }
}
