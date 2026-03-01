import SwiftUI
import HestiaShared
import Combine

@MainActor
class MacCloudSettingsViewModel: ObservableObject {
    // MARK: - Published State

    @Published var providers: [CloudProvider] = []
    @Published var effectiveCloudState: String = "disabled"
    @Published var isLoading: Bool = false
    @Published var error: String?

    @Published var showingAddProvider: Bool = false
    @Published var isAddingProvider: Bool = false

    @Published var isCheckingHealth: Bool = false
    @Published var healthCheckResult: String?

    @Published var usage: CloudUsageSummaryResponse?
    @Published var isLoadingUsage: Bool = false

    // MARK: - Dependencies

    private let client: APIClient

    // MARK: - Computed Properties

    var hasProviders: Bool { !providers.isEmpty }

    var activeProviderCount: Int {
        providers.filter { $0.isActive }.count
    }

    var effectiveStateDisplay: String {
        switch effectiveCloudState {
        case "enabled_full": return "Full Cloud"
        case "enabled_smart": return "Smart Hybrid"
        default: return "Local Only"
        }
    }

    var effectiveStateColor: Color {
        switch effectiveCloudState {
        case "enabled_full": return MacColors.healthGreen
        case "enabled_smart": return MacColors.healthAmber
        default: return MacColors.textFaint
        }
    }

    // MARK: - Init

    init(client: APIClient = .shared) {
        self.client = client
    }

    // MARK: - Data Loading

    func refresh() async {
        isLoading = true
        error = nil

        do {
            let response = try await client.listCloudProviders()
            providers = response.providers.map { $0.toCloudProvider() }
            effectiveCloudState = response.cloudState
        } catch {
            self.error = "Failed to load providers"
            #if DEBUG
            print("[MacCloudSettingsVM] Error: \(error)")
            #endif
        }

        isLoading = false
    }

    // MARK: - Provider Management

    func addProvider(type: CloudProvider.ProviderType, apiKey: String, state: CloudProvider.ProviderState, modelId: String?) async -> Bool {
        isAddingProvider = true
        error = nil

        let apiProvider = APICloudProvider(rawValue: type.rawValue) ?? .anthropic
        let apiState = state.apiState

        do {
            _ = try await client.addCloudProvider(apiProvider, apiKey: apiKey, state: apiState, modelId: modelId)
            await refresh()
            isAddingProvider = false
            return true
        } catch {
            self.error = "Failed to add provider"
            #if DEBUG
            print("[MacCloudSettingsVM] Error adding: \(error)")
            #endif
            isAddingProvider = false
            return false
        }
    }

    func removeProvider(_ provider: CloudProvider) async -> Bool {
        error = nil

        guard let apiProvider = APICloudProvider(rawValue: provider.provider.rawValue) else {
            return false
        }

        do {
            _ = try await client.removeCloudProvider(apiProvider)
            await refresh()
            return true
        } catch {
            self.error = "Failed to remove provider"
            #if DEBUG
            print("[MacCloudSettingsVM] Error removing: \(error)")
            #endif
            return false
        }
    }

    func updateState(_ provider: CloudProvider, newState: CloudProvider.ProviderState) async {
        error = nil

        guard let apiProvider = APICloudProvider(rawValue: provider.provider.rawValue) else { return }

        do {
            _ = try await client.updateCloudProviderState(apiProvider, state: newState.apiState)
            await refresh()
        } catch {
            self.error = "Failed to update state"
            #if DEBUG
            print("[MacCloudSettingsVM] Error updating state: \(error)")
            #endif
        }
    }

    func updateModel(_ provider: CloudProvider, modelId: String) async {
        error = nil

        guard let apiProvider = APICloudProvider(rawValue: provider.provider.rawValue) else { return }

        do {
            _ = try await client.updateCloudProviderModel(apiProvider, modelId: modelId)
            await refresh()
        } catch {
            self.error = "Failed to update model"
            #if DEBUG
            print("[MacCloudSettingsVM] Error updating model: \(error)")
            #endif
        }
    }

    // MARK: - Health Check

    func checkHealth(_ provider: CloudProvider) async {
        isCheckingHealth = true
        healthCheckResult = nil

        guard let apiProvider = APICloudProvider(rawValue: provider.provider.rawValue) else {
            isCheckingHealth = false
            return
        }

        do {
            let result = try await client.checkCloudProviderHealth(apiProvider)
            healthCheckResult = result.healthy ? "Healthy" : "Unhealthy: \(result.message)"
            await refresh()
        } catch {
            healthCheckResult = "Check failed"
            #if DEBUG
            print("[MacCloudSettingsVM] Health check error: \(error)")
            #endif
        }

        isCheckingHealth = false
    }

    // MARK: - Usage

    func loadUsage(days: Int = 30) async {
        isLoadingUsage = true

        do {
            usage = try await client.getCloudUsage(days: days)
        } catch {
            #if DEBUG
            print("[MacCloudSettingsVM] Usage error: \(error)")
            #endif
        }

        isLoadingUsage = false
    }
}
