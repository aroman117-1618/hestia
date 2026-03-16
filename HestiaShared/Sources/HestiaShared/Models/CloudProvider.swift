import SwiftUI

/// Local model representing a cloud LLM provider configuration
public struct CloudProvider: Identifiable, Equatable, Sendable {
    public let id: String
    public let provider: ProviderType
    public var state: ProviderState
    public var activeModelId: String?
    public var availableModels: [String]
    public var hasApiKey: Bool
    public var healthStatus: String
    public var lastHealthCheck: Date?
    public let createdAt: Date
    public var updatedAt: Date

    public init(id: String, provider: ProviderType, state: ProviderState, activeModelId: String?, availableModels: [String], hasApiKey: Bool, healthStatus: String, lastHealthCheck: Date?, createdAt: Date, updatedAt: Date) {
        self.id = id
        self.provider = provider
        self.state = state
        self.activeModelId = activeModelId
        self.availableModels = availableModels
        self.hasApiKey = hasApiKey
        self.healthStatus = healthStatus
        self.lastHealthCheck = lastHealthCheck
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    /// Supported cloud providers
    public enum ProviderType: String, CaseIterable, Identifiable, Sendable {
        case anthropic
        case openai
        case google

        public var id: String { rawValue }

        public var displayName: String {
            switch self {
            case .anthropic: return "Anthropic"
            case .openai: return "OpenAI"
            case .google: return "Google"
            }
        }

        public var iconName: String {
            switch self {
            case .anthropic: return "brain.head.profile"
            case .openai: return "cpu"
            case .google: return "globe"
            }
        }

        public var color: Color {
            switch self {
            case .anthropic: return .anthropicBrand
            case .openai: return .openAIBrand
            case .google: return .googleBrand
            }
        }

        public var modelPrefix: String {
            switch self {
            case .anthropic: return "claude"
            case .openai: return "gpt"
            case .google: return "gemini"
            }
        }
    }

    /// Provider routing state
    public enum ProviderState: String, CaseIterable, Identifiable, Sendable {
        case disabled
        case enabledFull
        case enabledSmart

        public var id: String { rawValue }

        public var displayName: String {
            switch self {
            case .disabled: return "Disabled"
            case .enabledFull: return "Full Cloud"
            case .enabledSmart: return "Smart Hybrid"
            }
        }

        public var description: String {
            switch self {
            case .disabled: return "Local models only"
            case .enabledFull: return "All queries use this cloud provider"
            case .enabledSmart: return "Local first, cloud fallback on failure or large queries"
            }
        }

        public var color: Color {
            switch self {
            case .disabled: return .white.opacity(0.4)
            case .enabledFull: return .healthyGreen
            case .enabledSmart: return .warningYellow
            }
        }

        /// Convert to API enum
        public var apiState: APICloudProviderState {
            switch self {
            case .disabled: return .disabled
            case .enabledFull: return .enabledFull
            case .enabledSmart: return .enabledSmart
            }
        }

        /// Create from API enum
        public init(from apiState: APICloudProviderState) {
            switch apiState {
            case .disabled: self = .disabled
            case .enabledFull: self = .enabledFull
            case .enabledSmart: self = .enabledSmart
            }
        }
    }

    /// Whether this provider is healthy
    public var isHealthy: Bool {
        healthStatus == "healthy"
    }

    /// Whether this provider is active (not disabled)
    public var isActive: Bool {
        state != .disabled
    }

    /// Human-readable model name from model ID
    public var activeModelDisplayName: String {
        guard let modelId = activeModelId else { return "Default" }
        return modelId
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .capitalized
    }
}

// MARK: - Conversion from API Response

extension CloudProviderResponse {
    public func toCloudProvider() -> CloudProvider {
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
