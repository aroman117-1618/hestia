import Foundation

// MARK: - Learning Metrics API Response Types

struct MetaMonitorReportResponse: Codable {
    let data: MetaMonitorReport?
}

struct MetaMonitorReport: Codable {
    let id: String?
    let userId: String?
    let timestamp: String?
    let status: String?
    let totalOutcomes: Int?
    let positiveRatio: Double?
    let confusionSessions: [String]?
    let avgLatencyMs: Double?
    let latencyTrend: String?
    let sampleSizeSufficient: Bool?

    enum CodingKeys: String, CodingKey {
        case id, timestamp, status
        case userId = "user_id"
        case totalOutcomes = "total_outcomes"
        case positiveRatio = "positive_ratio"
        case confusionSessions = "confusion_sessions"
        case avgLatencyMs = "avg_latency_ms"
        case latencyTrend = "latency_trend"
        case sampleSizeSufficient = "sample_size_sufficient"
    }
}

struct MemoryHealthResponse: Codable {
    let data: MemoryHealthSnapshot?
}

struct MemoryHealthSnapshot: Codable {
    let id: String?
    let userId: String?
    let timestamp: String?
    let chunkCount: Int?
    let chunkCountBySource: [String: Int]?
    let redundancyEstimatePct: Double?
    let entityCount: Int?
    let factCount: Int?
    let staleEntityCount: Int?
    let contradictionCount: Int?
    let communityCount: Int?

    enum CodingKeys: String, CodingKey {
        case id, timestamp
        case userId = "user_id"
        case chunkCount = "chunk_count"
        case chunkCountBySource = "chunk_count_by_source"
        case redundancyEstimatePct = "redundancy_estimate_pct"
        case entityCount = "entity_count"
        case factCount = "fact_count"
        case staleEntityCount = "stale_entity_count"
        case contradictionCount = "contradiction_count"
        case communityCount = "community_count"
    }
}

struct TriggerAlertsResponse: Codable {
    let data: [TriggerAlert]
}

struct TriggerAlert: Codable, Identifiable {
    let id: String
    let userId: String?
    let triggerName: String
    let currentValue: Double
    let thresholdValue: Double
    let direction: String
    let message: String
    let timestamp: String
    let acknowledged: Bool

    enum CodingKeys: String, CodingKey {
        case id, direction, message, timestamp, acknowledged
        case userId = "user_id"
        case triggerName = "trigger_name"
        case currentValue = "current_value"
        case thresholdValue = "threshold_value"
    }
}
