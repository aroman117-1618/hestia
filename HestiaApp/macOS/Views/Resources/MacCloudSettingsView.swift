import SwiftUI
import HestiaShared

struct MacCloudSettingsView: View {
    @StateObject private var viewModel = MacCloudSettingsViewModel()
    @State private var selectedProvider: CloudProvider?

    var body: some View {
        HStack(spacing: 0) {
            // Provider list (sidebar)
            providerList
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 320)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }

            // Detail pane
            if let provider = selectedProvider {
                MacCloudProviderDetailView(
                    provider: provider,
                    viewModel: viewModel
                )
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }
            } else {
                noSelectionView
                    .background(MacColors.panelBackground)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                    .overlay {
                        RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                            .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                    }
            }
        }
        .padding(MacSpacing.xl)
        .task {
            await viewModel.refresh()
            selectedProvider = viewModel.providers.first
        }
        .onChange(of: viewModel.providers) {
            if let current = selectedProvider {
                selectedProvider = viewModel.providers.first { $0.id == current.id } ?? viewModel.providers.first
            } else {
                selectedProvider = viewModel.providers.first
            }
        }
        .sheet(isPresented: $viewModel.showingAddProvider) {
            MacAddCloudProviderView(viewModel: viewModel)
        }
    }

    // MARK: - Provider List

    private var providerList: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Providers")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                Button {
                    viewModel.showingAddProvider = true
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.amberAccent)
                }
                .buttonStyle(.hestia)
            }
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.md)

            // State badge
            HStack(spacing: MacSpacing.xs) {
                Circle()
                    .fill(viewModel.effectiveStateColor)
                    .frame(width: 6, height: 6)
                Text(viewModel.effectiveStateDisplay)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
                Spacer()
            }
            .padding(.horizontal, MacSpacing.lg)
            .padding(.bottom, MacSpacing.sm)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            // Provider rows
            if viewModel.isLoading && viewModel.providers.isEmpty {
                Spacer()
                ProgressView()
                    .controlSize(.small)
                    .tint(MacColors.amberAccent)
                Spacer()
            } else if viewModel.providers.isEmpty {
                Spacer()
                VStack(spacing: MacSpacing.sm) {
                    Image(systemName: "cloud.slash")
                        .font(.system(size: 28))
                        .foregroundStyle(MacColors.textFaint)
                    Text("No providers")
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textSecondary)
                }
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 2) {
                        ForEach(viewModel.providers) { provider in
                            providerRow(provider)
                        }
                    }
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.top, MacSpacing.sm)
                }
            }
        }
    }

    private func providerRow(_ provider: CloudProvider) -> some View {
        let isSelected = selectedProvider?.id == provider.id

        return Button {
            selectedProvider = provider
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: provider.provider.iconName)
                    .font(.system(size: 14))
                    .foregroundStyle(provider.isActive ? MacColors.healthGreen : MacColors.textFaint)
                    .frame(width: 20)

                VStack(alignment: .leading, spacing: 2) {
                    Text(provider.provider.displayName)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(MacColors.textPrimary)

                    Text(provider.state.displayName)
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)
                }

                Spacer()

                Circle()
                    .fill(provider.healthStatus == "healthy" ? MacColors.healthGreen :
                          provider.healthStatus == "unknown" ? MacColors.textFaint :
                          MacColors.healthRed)
                    .frame(width: 6, height: 6)
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 8)
            .background(isSelected ? MacColors.activeTabBackground : Color.clear)
            .cornerRadius(MacCornerRadius.treeItem)
        }
        .buttonStyle(.hestia)
    }

    // MARK: - No Selection

    private var noSelectionView: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "cloud")
                .font(.system(size: 40))
                .foregroundStyle(MacColors.textFaint)
            Text("Select a provider")
                .font(.system(size: 14))
                .foregroundStyle(MacColors.textSecondary)
            if viewModel.providers.isEmpty {
                Button {
                    viewModel.showingAddProvider = true
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "plus")
                        Text("Add Provider")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.activeTabBackground)
                    .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.hestia)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
