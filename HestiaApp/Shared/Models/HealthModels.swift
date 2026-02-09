import Foundation

// MARK: - Health Sync API Models

/// A single health metric payload for sync to backend
struct HealthMetricPayload: Codable {
    let metricType: String
    let value: Double
    let unit: String
    let startDate: String
    let endDate: String
    let source: String
    let metadata: [String: AnyCodableValue]?

    init(
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
struct HealthSyncRequest: Codable {
    let metrics: [HealthMetricPayload]
    let syncDate: String

    init(metrics: [HealthMetricPayload], syncDate: Date = Date()) {
        self.metrics = metrics
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        self.syncDate = formatter.string(from: syncDate)
    }
}

/// Response from POST /v1/health_data/sync
struct HealthSyncResponse: Codable {
    let syncId: String
    let metricsReceived: Int
    let metricsStored: Int
    let metricsDeduplicated: Int
    let durationMs: Double
}

// MARK: - Coaching Preferences API Models

/// Coaching preferences response from GET /v1/health_data/coaching
struct CoachingPreferencesResponse: Codable {
    let preferences: CoachingPreferencesData
    let updatedAt: String
}

/// The coaching preferences data
struct CoachingPreferencesData: Codable {
    let enabled: Bool
    let activityCoaching: Bool
    let sleepCoaching: Bool
    let nutritionCoaching: Bool
    let heartCoaching: Bool
    let mindfulnessCoaching: Bool
    let dailySummary: Bool
    let summaryTime: String
    let goalAlerts: Bool
    let anomalyAlerts: Bool
    let dailyStepGoal: Int
    let dailyActiveCalGoal: Int
    let sleepHoursGoal: Double
    let dailyWaterMlGoal: Int
    let coachingTone: String
}

/// Request body for POST /v1/health_data/coaching
struct CoachingPreferencesUpdateRequest: Codable {
    let enabled: Bool?
    let activityCoaching: Bool?
    let sleepCoaching: Bool?
    let nutritionCoaching: Bool?
    let heartCoaching: Bool?
    let mindfulnessCoaching: Bool?
    let dailySummary: Bool?
    let summaryTime: String?
    let goalAlerts: Bool?
    let anomalyAlerts: Bool?
    let dailyStepGoal: Int?
    let dailyActiveCalGoal: Int?
    let sleepHoursGoal: Double?
    let dailyWaterMlGoal: Int?
    let coachingTone: String?

    init(
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
struct SyncHistoryItem: Codable, Identifiable {
    let syncId: String
    let syncDate: String
    let metricsReceived: Int
    let metricsStored: Int
    let timestamp: String

    var id: String { syncId }
}

/// Response from GET /v1/health_data/sync/history
struct SyncHistoryResponse: Codable {
    let syncs: [SyncHistoryItem]
    let total: Int
}
