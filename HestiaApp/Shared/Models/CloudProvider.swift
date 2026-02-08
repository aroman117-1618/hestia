import SwiftUI

/// Local model representing a cloud LLM provider configuration
struct CloudProvider: Identifiable, Equatable {
    let id: String
    let provider: ProviderType
    var state: ProviderState
    var activeModelId: String?
    var availableModels: [String]
    var hasApiKey: Bool
    var healthStatus: String
    var lastHealthCheck: Date?
    let createdAt: Date
    var updatedAt: Date

    /// Supported cloud providers
    enum ProviderType: String, CaseIterable, Identifiable {
        case anthropic
        case openai
        case google

        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .anthropic: return "Anthropic"
            case .openai: return "OpenAI"
            case .google: return "Google"
            }
        }

        var iconName: String {
            switch self {
            case .anthropic: return "brain.head.profile"
            case .openai: return "cpu"
            case .google: return "globe"
            }
        }

        var color: Color {
            switch self {
            case .anthropic: return .anthropicBrand
            case .openai: return .openAIBrand
            case .google: return .googleBrand
            }
        }

        var modelPrefix: String {
            switch self {
            case .anthropic: return "claude"
            case .openai: return "gpt"
            case .google: return "gemini"
            }
        }
    }

    /// Provider routing state
    enum ProviderState: String, CaseIterable, Identifiable {
        case disabled
        case enabledFull
        case enabledSmart

        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .disabled: return "Disabled"
            case .enabledFull: return "Full Cloud"
            case .enabledSmart: return "Smart Hybrid"
            }
        }

        var description: String {
            switch self {
            case .disabled: return "Local models only"
            case .enabledFull: return "All queries use this cloud provider"
            case .enabledSmart: return "Local first, cloud fallback on failure or large queries"
            }
        }

        var color: Color {
            switch self {
            case .disabled: return .white.opacity(0.4)
            case .enabledFull: return .healthyGreen
            case .enabledSmart: return .warningYellow
            }
        }

        /// Convert to API enum
        var apiState: APICloudProviderState {
            switch self {
            case .disabled: return .disabled
            case .enabledFull: return .enabledFull
            case .enabledSmart: return .enabledSmart
            }
        }

        /// Create from API enum
        init(from apiState: APICloudProviderState) {
            switch apiState {
            case .disabled: self = .disabled
            case .enabledFull: self = .enabledFull
            case .enabledSmart: self = .enabledSmart
            }
        }
    }

    /// Whether this provider is healthy
    var isHealthy: Bool {
        healthStatus == "healthy"
    }

    /// Whether this provider is active (not disabled)
    var isActive: Bool {
        state != .disabled
    }

    /// Human-readable model name from model ID
    var activeModelDisplayName: String {
        guard let modelId = activeModelId else { return "Default" }
        return modelId
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .capitalized
    }
}

// MARK: - Conversion from API Response

extension CloudProviderResponse {
    func toCloudProvider() -> CloudProvider {
        let providerType = CloudProvider.ProviderType(rawValue: provider.rawValue) ?? .anthropic
        let providerState = CloudProvider.ProviderState(from: state)

        return CloudProvider(
            id: id,
            provider: providerType,
            state: providerState,
            activeModelId: activeModelId,
            availableModels: availableModels,
            hasApiKey: hasApiKey,
            healthStatus: healthStatus,
            lastHealthCheck: lastHealthCheck,
            createdAt: createdAt,
            updatedAt: updatedAt
        )
    }
}
