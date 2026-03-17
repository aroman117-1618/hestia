import Foundation

// MARK: - Health Sync API Models

/// A single health metric payload for sync to backend
public struct HealthMetricPayload: Codable, Sendable {
    public let metricType: String
    public let value: Double
    public let unit: String
    public let startDate: String
    public let endDate: String
    public let source: String
    public let metadata: [String: AnyCodableValue]?

    public init(
        metricType: String,
        value: Double,
        unit: String,
        startDate: Date,
        endDate: Date,
        source: String = "Apple Health",
        metadata: [String: AnyCodableValue]? = nil
    ) {
        self.metricType = metricType
        self.value = value
        self.unit = unit
        self.startDate = ISO8601DateFormatter().string(from: startDate)
        self.endDate = ISO8601DateFormatter().string(from: endDate)
        self.source = source
        self.metadata = metadata
    }
}

/// Request body for POST /v1/health_data/sync
public struct HealthSyncRequest: Codable, Sendable {
    public let metrics: [HealthMetricPayload]
    public let syncDate: String

    public init(metrics: [HealthMetricPayload], syncDate: Date = Date()) {
        self.metrics = metrics
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        self.syncDate = formatter.string(from: syncDate)
    }
}

/// Response from POST /v1/health_data/sync
public struct HealthSyncResponse: Codable, Sendable {
    public let syncId: String
    public let metricsReceived: Int
    public let metricsStored: Int
    public let metricsDeduplicated: Int
    public let durationMs: Double

    public init(syncId: String, metricsReceived: Int, metricsStored: Int, metricsDeduplicated: Int, durationMs: Double) {
        self.syncId = syncId
        self.metricsReceived = metricsReceived
        self.metricsStored = metricsStored
        self.metricsDeduplicated = metricsDeduplicated
        self.durationMs = durationMs
    }
}

// MARK: - Coaching Preferences API Models

/// Coaching preferences response from GET /v1/health_data/coaching
public struct CoachingPreferencesResponse: Codable, Sendable {
    public let preferences: CoachingPreferencesData
    public let updatedAt: String

    public init(preferences: CoachingPreferencesData, updatedAt: String) {
        self.preferences = preferences
        self.updatedAt = updatedAt
    }
}

/// The coaching preferences data
public struct CoachingPreferencesData: Codable, Sendable {
    public let enabled: Bool
    public let activityCoaching: Bool
    public let sleepCoaching: Bool
    public let nutritionCoaching: Bool
    public let heartCoaching: Bool
    public let mindfulnessCoaching: Bool
    public let dailySummary: Bool
    public let summaryTime: String
    public let goalAlerts: Bool
    public let anomalyAlerts: Bool
    public let dailyStepGoal: Int
    public let dailyActiveCalGoal: Int
    public let sleepHoursGoal: Double
    public let dailyWaterMlGoal: Int
    public let coachingTone: String

    public init(enabled: Bool, activityCoaching: Bool, sleepCoaching: Bool, nutritionCoaching: Bool, heartCoaching: Bool, mindfulnessCoaching: Bool, dailySummary: Bool, summaryTime: String, goalAlerts: Bool, anomalyAlerts: Bool, dailyStepGoal: Int, dailyActiveCalGoal: Int, sleepHoursGoal: Double, dailyWaterMlGoal: Int, coachingTone: String) {
        self.enabled = enabled
        self.activityCoaching = activityCoaching
        self.sleepCoaching = sleepCoaching
        self.nutritionCoaching = nutritionCoaching
        self.heartCoaching = heartCoaching
        self.mindfulnessCoaching = mindfulnessCoaching
        self.dailySummary = dailySummary
        self.summaryTime = summaryTime
        self.goalAlerts = goalAlerts
        self.anomalyAlerts = anomalyAlerts
        self.dailyStepGoal = dailyStepGoal
        self.dailyActiveCalGoal = dailyActiveCalGoal
        self.sleepHoursGoal = sleepHoursGoal
        self.dailyWaterMlGoal = dailyWaterMlGoal
        self.coachingTone = coachingTone
    }
}

/// Request body for POST /v1/health_data/coaching
public struct CoachingPreferencesUpdateRequest: Codable, Sendable {
    public let enabled: Bool?
    public let activityCoaching: Bool?
    public let sleepCoaching: Bool?
    public let nutritionCoaching: Bool?
    public let heartCoaching: Bool?
    public let mindfulnessCoaching: Bool?
    public let dailySummary: Bool?
    public let summaryTime: String?
    public let goalAlerts: Bool?
    public let anomalyAlerts: Bool?
    public let dailyStepGoal: Int?
    public let dailyActiveCalGoal: Int?
    public let sleepHoursGoal: Double?
    public let dailyWaterMlGoal: Int?
    public let coachingTone: String?

    public init(
        enabled: Bool? = nil,
        activityCoaching: Bool? = nil,
        sleepCoaching: Bool? = nil,
        nutritionCoaching: Bool? = nil,
        heartCoaching: Bool? = nil,
        mindfulnessCoaching: Bool? = nil,
        dailySummary: Bool? = nil,
        summaryTime: String? = nil,
        goalAlerts: Bool? = nil,
        anomalyAlerts: Bool? = nil,
        dailyStepGoal: Int? = nil,
        dailyActiveCalGoal: Int? = nil,
        sleepHoursGoal: Double? = nil,
        dailyWaterMlGoal: Int? = nil,
        coachingTone: String? = nil
    ) {
        self.enabled = enabled
        self.activityCoaching = activityCoaching
        self.sleepCoaching = sleepCoaching
        self.nutritionCoaching = nutritionCoaching
        self.heartCoaching = heartCoaching
        self.mindfulnessCoaching = mindfulnessCoaching
        self.dailySummary = dailySummary
        self.summaryTime = summaryTime
        self.goalAlerts = goalAlerts
        self.anomalyAlerts = anomalyAlerts
        self.dailyStepGoal = dailyStepGoal
        self.dailyActiveCalGoal = dailyActiveCalGoal
        self.sleepHoursGoal = sleepHoursGoal
        self.dailyWaterMlGoal = dailyWaterMlGoal
        self.coachingTone = coachingTone
    }
}

// MARK: - Health Sync History

/// A single sync history entry
public struct SyncHistoryItem: Codable, Identifiable, Sendable {
    public let syncId: String
    public let syncDate: String
    public let metricsReceived: Int
    public let metricsStored: Int
    public let timestamp: String

    public var id: String { syncId }

    public init(syncId: String, syncDate: String, metricsReceived: Int, metricsStored: Int, timestamp: String) {
        self.syncId = syncId
        self.syncDate = syncDate
        self.metricsReceived = metricsReceived
        self.metricsStored = metricsStored
        self.timestamp = timestamp
    }
}

/// Response from GET /v1/health_data/sync/history
public struct SyncHistoryResponse: Codable, Sendable {
    public let syncs: [SyncHistoryItem]
    public let total: Int

    public init(syncs: [SyncHistoryItem], total: Int) {
        self.syncs = syncs
        self.total = total
    }
}
