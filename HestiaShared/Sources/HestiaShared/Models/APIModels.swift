import Foundation

// MARK: - Orders API Models

/// API-specific frequency type for JSON serialization
public enum APIOrderFrequencyType: String, Codable, CaseIterable, Sendable {
    case once
    case daily
    case weekly
    case monthly
    case custom
}

/// API-specific order status for JSON serialization
public enum APIOrderStatus: String, Codable, CaseIterable, Sendable {
    case active
    case inactive
}

/// API-specific execution status for JSON serialization
public enum APIExecutionStatus: String, Codable, CaseIterable, Sendable {
    case scheduled
    case running
    case success
    case failed
}

/// API-specific MCP resource for JSON serialization
public enum APIMCPResource: String, Codable, CaseIterable, Sendable {
    case firecrawl
    case github
    case appleNews = "apple_news"
    case fidelity
    case calendar
    case email
    case reminder
    case note
    case shortcut
}

public struct OrderFrequencyAPI: Codable, Sendable {
    public let type: APIOrderFrequencyType
    public let minutes: Int?

    public init(type: APIOrderFrequencyType, minutes: Int?) {
        self.type = type
        self.minutes = minutes
    }
}

public struct OrderExecutionSummary: Codable, Identifiable, Sendable {
    public let executionId: String
    public let timestamp: Date
    public let status: APIExecutionStatus

    public var id: String { executionId }

    public init(executionId: String, timestamp: Date, status: APIExecutionStatus) {
        self.executionId = executionId
        self.timestamp = timestamp
        self.status = status
    }
}

public struct OrderCreateRequest: Codable, Sendable {
    public let name: String
    public let prompt: String
    public let scheduledTime: String
    public let frequency: OrderFrequencyAPI
    public let resources: [APIMCPResource]
    public let status: APIOrderStatus

    public init(name: String, prompt: String, scheduledTime: String, frequency: OrderFrequencyAPI, resources: [APIMCPResource], status: APIOrderStatus = .active) {
        self.name = name
        self.prompt = prompt
        self.scheduledTime = scheduledTime
        self.frequency = frequency
        self.resources = resources
        self.status = status
    }
}

public struct OrderUpdateRequest: Codable, Sendable {
    public let name: String?
    public let prompt: String?
    public let scheduledTime: String?
    public let frequency: OrderFrequencyAPI?
    public let resources: [APIMCPResource]?
    public let status: APIOrderStatus?

    public init(name: String? = nil, prompt: String? = nil, scheduledTime: String? = nil, frequency: OrderFrequencyAPI? = nil, resources: [APIMCPResource]? = nil, status: APIOrderStatus? = nil) {
        self.name = name
        self.prompt = prompt
        self.scheduledTime = scheduledTime
        self.frequency = frequency
        self.resources = resources
        self.status = status
    }
}

public struct OrderResponse: Codable, Identifiable, Sendable {
    public let orderId: String
    public let name: String
    public let prompt: String
    public let scheduledTime: String
    public let frequency: OrderFrequencyAPI
    public let resources: [APIMCPResource]
    public let status: APIOrderStatus
    public let nextExecution: Date?
    public let lastExecution: OrderExecutionSummary?
    public let createdAt: Date
    public let updatedAt: Date

    public var id: String { orderId }

    public init(orderId: String, name: String, prompt: String, scheduledTime: String, frequency: OrderFrequencyAPI, resources: [APIMCPResource], status: APIOrderStatus, nextExecution: Date?, lastExecution: OrderExecutionSummary?, createdAt: Date, updatedAt: Date) {
        self.orderId = orderId
        self.name = name
        self.prompt = prompt
        self.scheduledTime = scheduledTime
        self.frequency = frequency
        self.resources = resources
        self.status = status
        self.nextExecution = nextExecution
        self.lastExecution = lastExecution
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public struct OrderListResponse: Codable, Sendable {
    public let orders: [OrderResponse]
    public let total: Int
    public let limit: Int
    public let offset: Int

    public init(orders: [OrderResponse], total: Int, limit: Int, offset: Int) {
        self.orders = orders
        self.total = total
        self.limit = limit
        self.offset = offset
    }
}

public struct OrderDeleteResponse: Codable, Sendable {
    public let orderId: String
    public let deleted: Bool
    public let message: String

    public init(orderId: String, deleted: Bool, message: String) {
        self.orderId = orderId
        self.deleted = deleted
        self.message = message
    }
}

public struct OrderExecutionDetail: Codable, Identifiable, Sendable {
    public let executionId: String
    public let timestamp: Date
    public let status: APIExecutionStatus
    public let hestiaRead: String?
    public let fullResponse: String?
    public let durationMs: Double?
    public let resourcesUsed: [APIMCPResource]

    public var id: String { executionId }

    public init(executionId: String, timestamp: Date, status: APIExecutionStatus, hestiaRead: String?, fullResponse: String?, durationMs: Double?, resourcesUsed: [APIMCPResource]) {
        self.executionId = executionId
        self.timestamp = timestamp
        self.status = status
        self.hestiaRead = hestiaRead
        self.fullResponse = fullResponse
        self.durationMs = durationMs
        self.resourcesUsed = resourcesUsed
    }
}

public struct OrderExecutionsResponse: Codable, Sendable {
    public let orderId: String
    public let executions: [OrderExecutionDetail]
    public let total: Int
    public let limit: Int
    public let offset: Int

    public init(orderId: String, executions: [OrderExecutionDetail], total: Int, limit: Int, offset: Int) {
        self.orderId = orderId
        self.executions = executions
        self.total = total
        self.limit = limit
        self.offset = offset
    }
}

public struct OrderExecuteResponse: Codable, Sendable {
    public let orderId: String
    public let executionId: String
    public let status: APIExecutionStatus
    public let message: String

    public init(orderId: String, executionId: String, status: APIExecutionStatus, message: String) {
        self.orderId = orderId
        self.executionId = executionId
        self.status = status
        self.message = message
    }
}

// MARK: - Agent Profile API Models

/// API-specific snapshot reason for JSON serialization
public enum APISnapshotReason: String, Codable, Sendable {
    case edited
    case deleted
}

public struct AgentSnapshotSummary: Codable, Identifiable, Sendable {
    public let snapshotId: String
    public let snapshotDate: Date
    public let reason: APISnapshotReason

    public var id: String { snapshotId }

    public init(snapshotId: String, snapshotDate: Date, reason: APISnapshotReason) {
        self.snapshotId = snapshotId
        self.snapshotDate = snapshotDate
        self.reason = reason
    }
}

public struct AgentProfileResponse: Codable, Identifiable, Sendable {
    public let agentId: String
    public let slotIndex: Int
    public let name: String
    public let instructions: String
    public let gradientColor1: String
    public let gradientColor2: String
    public let isDefault: Bool
    public let canBeDeleted: Bool
    public let photoUrl: String?
    public let snapshots: [AgentSnapshotSummary]?
    public let createdAt: Date
    public let updatedAt: Date

    public var id: String { agentId }

    public init(agentId: String, slotIndex: Int, name: String, instructions: String, gradientColor1: String, gradientColor2: String, isDefault: Bool, canBeDeleted: Bool, photoUrl: String?, snapshots: [AgentSnapshotSummary]?, createdAt: Date, updatedAt: Date) {
        self.agentId = agentId
        self.slotIndex = slotIndex
        self.name = name
        self.instructions = instructions
        self.gradientColor1 = gradientColor1
        self.gradientColor2 = gradientColor2
        self.isDefault = isDefault
        self.canBeDeleted = canBeDeleted
        self.photoUrl = photoUrl
        self.snapshots = snapshots
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public struct AgentListResponse: Codable, Sendable {
    public let agents: [AgentProfileResponse]
    public let count: Int

    public init(agents: [AgentProfileResponse], count: Int) {
        self.agents = agents
        self.count = count
    }
}

public struct AgentUpdateRequest: Codable, Sendable {
    public let name: String
    public let instructions: String
    public let gradientColor1: String
    public let gradientColor2: String

    public init(name: String, instructions: String, gradientColor1: String, gradientColor2: String) {
        self.name = name
        self.instructions = instructions
        self.gradientColor1 = gradientColor1
        self.gradientColor2 = gradientColor2
    }
}

public struct AgentDeleteResponse: Codable, Sendable {
    public let slotIndex: Int
    public let resetToDefault: Bool
    public let defaultName: String
    public let snapshotCreated: Bool
    public let message: String

    public init(slotIndex: Int, resetToDefault: Bool, defaultName: String, snapshotCreated: Bool, message: String) {
        self.slotIndex = slotIndex
        self.resetToDefault = resetToDefault
        self.defaultName = defaultName
        self.snapshotCreated = snapshotCreated
        self.message = message
    }
}

public struct AgentPhotoResponse: Codable, Sendable {
    public let slotIndex: Int
    public let photoUrl: String?
    public let message: String

    public init(slotIndex: Int, photoUrl: String?, message: String) {
        self.slotIndex = slotIndex
        self.photoUrl = photoUrl
        self.message = message
    }
}

public struct AgentSnapshotDetail: Codable, Identifiable, Sendable {
    public let snapshotId: String
    public let snapshotDate: Date
    public let reason: APISnapshotReason
    public let name: String
    public let instructionsPreview: String

    public var id: String { snapshotId }

    public init(snapshotId: String, snapshotDate: Date, reason: APISnapshotReason, name: String, instructionsPreview: String) {
        self.snapshotId = snapshotId
        self.snapshotDate = snapshotDate
        self.reason = reason
        self.name = name
        self.instructionsPreview = instructionsPreview
    }
}

public struct AgentSnapshotsResponse: Codable, Sendable {
    public let slotIndex: Int
    public let snapshots: [AgentSnapshotDetail]
    public let count: Int
    public let retentionDays: Int

    public init(slotIndex: Int, snapshots: [AgentSnapshotDetail], count: Int, retentionDays: Int) {
        self.slotIndex = slotIndex
        self.snapshots = snapshots
        self.count = count
        self.retentionDays = retentionDays
    }
}

public struct AgentRestoreRequest: Codable, Sendable {
    public let snapshotId: String

    public init(snapshotId: String) {
        self.snapshotId = snapshotId
    }
}

public struct AgentRestoreResponse: Codable, Sendable {
    public let slotIndex: Int
    public let restoredFrom: String
    public let name: String
    public let message: String

    public init(slotIndex: Int, restoredFrom: String, name: String, message: String) {
        self.slotIndex = slotIndex
        self.restoredFrom = restoredFrom
        self.name = name
        self.message = message
    }
}

// MARK: - User Settings API Models

public struct QuietHours: Codable, Sendable {
    public let enabled: Bool
    public let start: String
    public let end: String

    public init(enabled: Bool = false, start: String = "22:00", end: String = "07:00") {
        self.enabled = enabled
        self.start = start
        self.end = end
    }
}

public struct PushNotificationSettings: Codable, Sendable {
    public let enabled: Bool
    public let orderAlerts: Bool
    public let proactiveBriefings: Bool
    public let quietHours: QuietHours

    public init(enabled: Bool = true, orderAlerts: Bool = true, proactiveBriefings: Bool = true, quietHours: QuietHours = QuietHours()) {
        self.enabled = enabled
        self.orderAlerts = orderAlerts
        self.proactiveBriefings = proactiveBriefings
        self.quietHours = quietHours
    }
}

public struct UserProfileResponse: Codable, Sendable {
    public let userId: String
    public let name: String
    public let description: String?
    public let photoUrl: String?
    public let createdAt: Date
    public let updatedAt: Date

    public init(userId: String, name: String, description: String?, photoUrl: String?, createdAt: Date, updatedAt: Date) {
        self.userId = userId
        self.name = name
        self.description = description
        self.photoUrl = photoUrl
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public struct UserProfileUpdateRequest: Codable, Sendable {
    public let name: String?
    public let description: String?

    public init(name: String? = nil, description: String? = nil) {
        self.name = name
        self.description = description
    }
}

public struct UserSettingsResponse: Codable, Sendable {
    public let pushNotifications: PushNotificationSettings
    public let defaultMode: String
    public let autoLockTimeoutMinutes: Int

    public init(pushNotifications: PushNotificationSettings, defaultMode: String, autoLockTimeoutMinutes: Int) {
        self.pushNotifications = pushNotifications
        self.defaultMode = defaultMode
        self.autoLockTimeoutMinutes = autoLockTimeoutMinutes
    }
}

public struct UserSettingsUpdateRequest: Codable, Sendable {
    public let pushNotifications: PushNotificationSettings?
    public let defaultMode: String?
    public let autoLockTimeoutMinutes: Int?

    public init(pushNotifications: PushNotificationSettings? = nil, defaultMode: String? = nil, autoLockTimeoutMinutes: Int? = nil) {
        self.pushNotifications = pushNotifications
        self.defaultMode = defaultMode
        self.autoLockTimeoutMinutes = autoLockTimeoutMinutes
    }
}

public struct UserSettingsUpdateResponse: Codable, Sendable {
    public let updated: Bool
    public let settings: UserSettingsResponse

    public init(updated: Bool, settings: UserSettingsResponse) {
        self.updated = updated
        self.settings = settings
    }
}

public enum PushEnvironment: String, Codable, Sendable {
    case production
    case sandbox
}

public struct PushTokenRequest: Codable, Sendable {
    public let pushToken: String
    public let deviceId: String
    public let environment: PushEnvironment

    public init(pushToken: String, deviceId: String, environment: PushEnvironment) {
        self.pushToken = pushToken
        self.deviceId = deviceId
        self.environment = environment
    }
}

public struct PushTokenResponse: Codable, Sendable {
    public let registered: Bool
    public let deviceId: String
    public let message: String

    public init(registered: Bool, deviceId: String, message: String) {
        self.registered = registered
        self.deviceId = deviceId
        self.message = message
    }
}

// MARK: - Cloud Provider API Models

/// Supported cloud LLM providers
public enum APICloudProvider: String, Codable, CaseIterable, Sendable {
    case anthropic
    case openai
    case google
}

/// Cloud provider operational state
public enum APICloudProviderState: String, Codable, CaseIterable, Sendable {
    case disabled
    case enabledFull = "enabled_full"
    case enabledSmart = "enabled_smart"
}

public struct CloudProviderAddRequest: Codable, Sendable {
    public let provider: APICloudProvider
    public let apiKey: String
    public let state: APICloudProviderState
    public let modelId: String?

    public init(provider: APICloudProvider, apiKey: String, state: APICloudProviderState = .enabledSmart, modelId: String? = nil) {
        self.provider = provider
        self.apiKey = apiKey
        self.state = state
        self.modelId = modelId
    }
}

public struct CloudProviderStateUpdateRequest: Codable, Sendable {
    public let state: APICloudProviderState

    public init(state: APICloudProviderState) {
        self.state = state
    }
}

public struct CloudProviderModelUpdateRequest: Codable, Sendable {
    public let modelId: String

    public init(modelId: String) {
        self.modelId = modelId
    }
}

public struct CloudModelInfo: Codable, Identifiable, Sendable {
    public let modelId: String
    public let provider: APICloudProvider
    public let displayName: String
    public let contextWindow: Int
    public let maxOutputTokens: Int
    public let costPer1kInput: Double
    public let costPer1kOutput: Double

    public var id: String { modelId }

    public init(modelId: String, provider: APICloudProvider, displayName: String, contextWindow: Int, maxOutputTokens: Int, costPer1kInput: Double, costPer1kOutput: Double) {
        self.modelId = modelId
        self.provider = provider
        self.displayName = displayName
        self.contextWindow = contextWindow
        self.maxOutputTokens = maxOutputTokens
        self.costPer1kInput = costPer1kInput
        self.costPer1kOutput = costPer1kOutput
    }
}

public struct CloudProviderResponse: Codable, Identifiable, Sendable {
    public let id: String
    public let provider: APICloudProvider
    public let state: APICloudProviderState
    public let activeModelId: String?
    public let availableModels: [String]
    public let hasApiKey: Bool
    public let healthStatus: String
    public let lastHealthCheck: Date?
    public let createdAt: Date
    public let updatedAt: Date

    public init(id: String, provider: APICloudProvider, state: APICloudProviderState, activeModelId: String?, availableModels: [String], hasApiKey: Bool, healthStatus: String, lastHealthCheck: Date?, createdAt: Date, updatedAt: Date) {
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
}

public struct CloudProviderListResponse: Codable, Sendable {
    public let providers: [CloudProviderResponse]
    public let count: Int
    public let cloudState: String

    public init(providers: [CloudProviderResponse], count: Int, cloudState: String) {
        self.providers = providers
        self.count = count
        self.cloudState = cloudState
    }
}

public struct CloudProviderDeleteResponse: Codable, Sendable {
    public let provider: APICloudProvider
    public let deleted: Bool
    public let message: String

    public init(provider: APICloudProvider, deleted: Bool, message: String) {
        self.provider = provider
        self.deleted = deleted
        self.message = message
    }
}

public struct CloudUsageSummaryResponse: Codable, Sendable {
    public let periodDays: Int
    public let totalRequests: Int
    public let totalTokensIn: Int
    public let totalTokensOut: Int
    public let totalCostUsd: Double
    public let byProvider: [String: CloudUsageBreakdown]?
    public let byModel: [String: CloudUsageBreakdown]?

    public init(periodDays: Int, totalRequests: Int, totalTokensIn: Int, totalTokensOut: Int, totalCostUsd: Double, byProvider: [String: CloudUsageBreakdown]?, byModel: [String: CloudUsageBreakdown]?) {
        self.periodDays = periodDays
        self.totalRequests = totalRequests
        self.totalTokensIn = totalTokensIn
        self.totalTokensOut = totalTokensOut
        self.totalCostUsd = totalCostUsd
        self.byProvider = byProvider
        self.byModel = byModel
    }
}

public struct CloudUsageBreakdown: Codable, Sendable {
    public let requests: Int?
    public let tokensIn: Int?
    public let tokensOut: Int?
    public let costUsd: Double?

    public init(requests: Int?, tokensIn: Int?, tokensOut: Int?, costUsd: Double?) {
        self.requests = requests
        self.tokensIn = tokensIn
        self.tokensOut = tokensOut
        self.costUsd = costUsd
    }
}

public struct CloudHealthCheckResponse: Codable, Sendable {
    public let provider: APICloudProvider
    public let healthy: Bool
    public let healthStatus: String
    public let message: String

    public init(provider: APICloudProvider, healthy: Bool, healthStatus: String, message: String) {
        self.provider = provider
        self.healthy = healthy
        self.healthStatus = healthStatus
        self.message = message
    }
}

// MARK: - Voice Journaling API Models (WS2)

/// Request body for POST /v1/voice/quality-check
public struct VoiceQualityCheckRequest: Codable, Sendable {
    public let transcript: String
    public let knownEntities: [String]?

    public init(transcript: String, knownEntities: [String]?) {
        self.transcript = transcript
        self.knownEntities = knownEntities
    }
}

/// A word flagged as potentially incorrect by the quality checker
public struct VoiceFlaggedWordResponse: Codable, Sendable {
    public let word: String
    public let position: Int
    public let confidence: Double
    public let suggestions: [String]
    public let reason: String

    /// Unique key for ForEach identification (avoids position-only collisions)
    public var uniqueKey: String { "\(position)-\(word)" }

    public init(word: String, position: Int, confidence: Double, suggestions: [String], reason: String) {
        self.word = word
        self.position = position
        self.confidence = confidence
        self.suggestions = suggestions
        self.reason = reason
    }
}

/// Response from POST /v1/voice/quality-check
public struct VoiceQualityCheckResponse: Codable, Sendable {
    public let transcript: String
    public let flaggedWords: [VoiceFlaggedWordResponse]
    public let overallConfidence: Double
    public let needsReview: Bool

    public init(transcript: String, flaggedWords: [VoiceFlaggedWordResponse], overallConfidence: Double, needsReview: Bool) {
        self.transcript = transcript
        self.flaggedWords = flaggedWords
        self.overallConfidence = overallConfidence
        self.needsReview = needsReview
    }
}

/// Request body for POST /v1/voice/journal-analyze
public struct VoiceJournalAnalyzeRequest: Codable, Sendable {
    public let transcript: String
    public let mode: String?

    public init(transcript: String, mode: String?) {
        self.transcript = transcript
        self.mode = mode
    }
}

/// Intent type extracted from journal entries
public enum APIVoiceIntentType: String, Codable, CaseIterable, Sendable {
    case actionItem = "action_item"
    case reminder
    case note
    case decision
    case reflection
    case followUp = "follow_up"
}

/// Cross-reference source for journal analysis
public enum APIVoiceCrossRefSource: String, Codable, CaseIterable, Sendable {
    case calendar
    case mail
    case memory
    case reminders
}

/// An intent extracted from a journal transcript
public struct VoiceJournalIntentResponse: Codable, Identifiable, Sendable {
    public let id: String
    public let intentType: APIVoiceIntentType
    public let content: String
    public let confidence: Double
    public let entities: [String]

    public init(id: String, intentType: APIVoiceIntentType, content: String, confidence: Double, entities: [String]) {
        self.id = id
        self.intentType = intentType
        self.content = content
        self.confidence = confidence
        self.entities = entities
    }
}

/// A cross-reference match from an external source
public struct VoiceCrossReferenceResponse: Codable, Sendable {
    public let source: APIVoiceCrossRefSource
    public let match: String
    public let relevance: Double
    public let details: [String: AnyCodableValue]?

    public init(source: APIVoiceCrossRefSource, match: String, relevance: Double, details: [String: AnyCodableValue]?) {
        self.source = source
        self.match = match
        self.relevance = relevance
        self.details = details
    }
}

/// An action plan item from journal analysis
public struct VoiceActionPlanItemResponse: Codable, Identifiable, Sendable {
    public let id: String
    public let action: String
    public let toolCall: String?
    public let arguments: [String: AnyCodableValue]?
    public let confidence: Double
    public let intentId: String?

    public init(id: String, action: String, toolCall: String?, arguments: [String: AnyCodableValue]?, confidence: Double, intentId: String?) {
        self.id = id
        self.action = action
        self.toolCall = toolCall
        self.arguments = arguments
        self.confidence = confidence
        self.intentId = intentId
    }
}

/// Response from POST /v1/voice/journal-analyze
public struct VoiceJournalAnalyzeResponse: Codable, Identifiable, Sendable {
    public let id: String
    public let transcript: String
    public let intents: [VoiceJournalIntentResponse]
    public let crossReferences: [VoiceCrossReferenceResponse]
    public let actionPlan: [VoiceActionPlanItemResponse]
    public let summary: String
    public let timestamp: String

    public init(id: String, transcript: String, intents: [VoiceJournalIntentResponse], crossReferences: [VoiceCrossReferenceResponse], actionPlan: [VoiceActionPlanItemResponse], summary: String, timestamp: String) {
        self.id = id
        self.transcript = transcript
        self.intents = intents
        self.crossReferences = crossReferences
        self.actionPlan = actionPlan
        self.summary = summary
        self.timestamp = timestamp
    }
}

/// Type-erased Codable value for dynamic JSON dicts (arguments, details)
public enum AnyCodableValue: Codable, Sendable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(String.self) { self = .string(v); return }
        if let v = try? container.decode(Int.self) { self = .int(v); return }
        if let v = try? container.decode(Double.self) { self = .double(v); return }
        if let v = try? container.decode(Bool.self) { self = .bool(v); return }
        if container.decodeNil() { self = .null; return }
        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported value type")
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let v): try container.encode(v)
        case .int(let v): try container.encode(v)
        case .double(let v): try container.encode(v)
        case .bool(let v): try container.encode(v)
        case .null: try container.encodeNil()
        }
    }

    public var stringValue: String? {
        if case .string(let v) = self { return v }
        return nil
    }
}

// MARK: - Generic API Response Wrapper

public struct EmptyResponse: Codable, Sendable {
    public init() {}
}

// MARK: - Conversion Extensions (API Models to Local Models)

extension OrderResponse {
    /// Convert API response to local Order model
    public func toOrder() -> Order {
        let localFrequency: OrderFrequency
        switch frequency.type {
        case .once: localFrequency = .once
        case .daily: localFrequency = .daily
        case .weekly: localFrequency = .weekly
        case .monthly: localFrequency = .monthly
        case .custom: localFrequency = .custom(minutes: frequency.minutes ?? 60)
        }

        let localResources: Set<MCPResource> = Set(resources.compactMap { apiResource in
            MCPResource(rawValue: apiResource.rawValue)
        })

        let localStatus: OrderStatus = (status == .active) ? .active : .inactive

        var localLastExecution: OrderExecution? = nil
        if let lastExec = lastExecution {
            localLastExecution = OrderExecution(
                id: UUID(uuidString: lastExec.executionId) ?? UUID(),
                orderId: UUID(uuidString: orderId) ?? UUID(),
                timestamp: lastExec.timestamp,
                status: ExecutionStatus(rawValue: lastExec.status.rawValue) ?? .scheduled,
                hestiaRead: nil,
                fullResponse: nil
            )
        }

        return Order(
            id: UUID(uuidString: orderId) ?? UUID(),
            name: name,
            prompt: prompt,
            scheduledTime: ISO8601DateFormatter().date(from: scheduledTime) ?? Date(),
            frequency: localFrequency,
            resources: localResources,
            orderStatus: localStatus,
            lastExecution: localLastExecution,
            createdAt: createdAt,
            updatedAt: updatedAt
        )
    }
}
