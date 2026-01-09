import Foundation

// MARK: - Orders API Models

/// API-specific frequency type for JSON serialization
enum APIOrderFrequencyType: String, Codable, CaseIterable {
    case once
    case daily
    case weekly
    case monthly
    case custom
}

/// API-specific order status for JSON serialization
enum APIOrderStatus: String, Codable, CaseIterable {
    case active
    case inactive
}

/// API-specific execution status for JSON serialization
enum APIExecutionStatus: String, Codable, CaseIterable {
    case scheduled
    case running
    case success
    case failed
}

/// API-specific MCP resource for JSON serialization
enum APIMCPResource: String, Codable, CaseIterable {
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

struct OrderFrequencyAPI: Codable {
    let type: APIOrderFrequencyType
    let minutes: Int?
}

struct OrderExecutionSummary: Codable, Identifiable {
    let executionId: String
    let timestamp: Date
    let status: APIExecutionStatus

    var id: String { executionId }
}

struct OrderCreateRequest: Codable {
    let name: String
    let prompt: String
    let scheduledTime: String
    let frequency: OrderFrequencyAPI
    let resources: [APIMCPResource]
    let status: APIOrderStatus

    init(name: String, prompt: String, scheduledTime: String, frequency: OrderFrequencyAPI, resources: [APIMCPResource], status: APIOrderStatus = .active) {
        self.name = name
        self.prompt = prompt
        self.scheduledTime = scheduledTime
        self.frequency = frequency
        self.resources = resources
        self.status = status
    }
}

struct OrderUpdateRequest: Codable {
    let name: String?
    let prompt: String?
    let scheduledTime: String?
    let frequency: OrderFrequencyAPI?
    let resources: [APIMCPResource]?
    let status: APIOrderStatus?
}

struct OrderResponse: Codable, Identifiable {
    let orderId: String
    let name: String
    let prompt: String
    let scheduledTime: String
    let frequency: OrderFrequencyAPI
    let resources: [APIMCPResource]
    let status: APIOrderStatus
    let nextExecution: Date?
    let lastExecution: OrderExecutionSummary?
    let createdAt: Date
    let updatedAt: Date

    var id: String { orderId }
}

struct OrderListResponse: Codable {
    let orders: [OrderResponse]
    let total: Int
    let limit: Int
    let offset: Int
}

struct OrderDeleteResponse: Codable {
    let orderId: String
    let deleted: Bool
    let message: String
}

struct OrderExecutionDetail: Codable, Identifiable {
    let executionId: String
    let timestamp: Date
    let status: APIExecutionStatus
    let hestiaRead: String?
    let fullResponse: String?
    let durationMs: Double?
    let resourcesUsed: [APIMCPResource]

    var id: String { executionId }
}

struct OrderExecutionsResponse: Codable {
    let orderId: String
    let executions: [OrderExecutionDetail]
    let total: Int
    let limit: Int
    let offset: Int
}

struct OrderExecuteResponse: Codable {
    let orderId: String
    let executionId: String
    let status: APIExecutionStatus
    let message: String
}

// MARK: - Agent Profile API Models

/// API-specific snapshot reason for JSON serialization
enum APISnapshotReason: String, Codable {
    case edited
    case deleted
}

struct AgentSnapshotSummary: Codable, Identifiable {
    let snapshotId: String
    let snapshotDate: Date
    let reason: APISnapshotReason

    var id: String { snapshotId }
}

struct AgentProfileResponse: Codable, Identifiable {
    let agentId: String
    let slotIndex: Int
    let name: String
    let instructions: String
    let gradientColor1: String
    let gradientColor2: String
    let isDefault: Bool
    let canBeDeleted: Bool
    let photoUrl: String?
    let snapshots: [AgentSnapshotSummary]?
    let createdAt: Date
    let updatedAt: Date

    var id: String { agentId }
}

struct AgentListResponse: Codable {
    let agents: [AgentProfileResponse]
    let count: Int
}

struct AgentUpdateRequest: Codable {
    let name: String
    let instructions: String
    let gradientColor1: String
    let gradientColor2: String
}

struct AgentDeleteResponse: Codable {
    let slotIndex: Int
    let resetToDefault: Bool
    let defaultName: String
    let snapshotCreated: Bool
    let message: String
}

struct AgentPhotoResponse: Codable {
    let slotIndex: Int
    let photoUrl: String?
    let message: String
}

struct AgentSnapshotDetail: Codable, Identifiable {
    let snapshotId: String
    let snapshotDate: Date
    let reason: APISnapshotReason
    let name: String
    let instructionsPreview: String

    var id: String { snapshotId }
}

struct AgentSnapshotsResponse: Codable {
    let slotIndex: Int
    let snapshots: [AgentSnapshotDetail]
    let count: Int
    let retentionDays: Int
}

struct AgentRestoreRequest: Codable {
    let snapshotId: String
}

struct AgentRestoreResponse: Codable {
    let slotIndex: Int
    let restoredFrom: String
    let name: String
    let message: String
}

// MARK: - User Settings API Models

struct QuietHours: Codable {
    let enabled: Bool
    let start: String
    let end: String

    init(enabled: Bool = false, start: String = "22:00", end: String = "07:00") {
        self.enabled = enabled
        self.start = start
        self.end = end
    }
}

struct PushNotificationSettings: Codable {
    let enabled: Bool
    let orderAlerts: Bool
    let proactiveBriefings: Bool
    let quietHours: QuietHours

    init(enabled: Bool = true, orderAlerts: Bool = true, proactiveBriefings: Bool = true, quietHours: QuietHours = QuietHours()) {
        self.enabled = enabled
        self.orderAlerts = orderAlerts
        self.proactiveBriefings = proactiveBriefings
        self.quietHours = quietHours
    }
}

struct UserProfileResponse: Codable {
    let userId: String
    let name: String
    let description: String?
    let photoUrl: String?
    let createdAt: Date
    let updatedAt: Date
}

struct UserProfileUpdateRequest: Codable {
    let name: String?
    let description: String?
}

struct UserSettingsResponse: Codable {
    let pushNotifications: PushNotificationSettings
    let defaultMode: String
    let autoLockTimeoutMinutes: Int
}

struct UserSettingsUpdateRequest: Codable {
    let pushNotifications: PushNotificationSettings?
    let defaultMode: String?
    let autoLockTimeoutMinutes: Int?
}

struct UserSettingsUpdateResponse: Codable {
    let updated: Bool
    let settings: UserSettingsResponse
}

enum PushEnvironment: String, Codable {
    case production
    case sandbox
}

struct PushTokenRequest: Codable {
    let pushToken: String
    let deviceId: String
    let environment: PushEnvironment
}

struct PushTokenResponse: Codable {
    let registered: Bool
    let deviceId: String
    let message: String
}

// MARK: - Generic API Response Wrapper

struct EmptyResponse: Codable {}

// MARK: - Conversion Extensions (API Models to Local Models)

extension OrderResponse {
    /// Convert API response to local Order model
    func toOrder() -> Order {
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
