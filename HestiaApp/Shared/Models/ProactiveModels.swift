import Foundation
import HestiaShared

// MARK: - Proactive Intelligence API Types

/// Mirrors backend PolicyResponse.
struct ProactivePolicyResponse: Codable {
    let interruptionPolicy: String
    let briefing: [String: AnyCodableValue]
    let quietHours: [String: AnyCodableValue]
    let patterns: [String: AnyCodableValue]
    let weather: [String: AnyCodableValue]
    let nextBriefing: String?
    let canInterruptNow: Bool

    enum CodingKeys: String, CodingKey {
        case interruptionPolicy = "interruption_policy"
        case briefing
        case quietHours = "quiet_hours"
        case patterns, weather
        case nextBriefing = "next_briefing"
        case canInterruptNow = "can_interrupt_now"
    }

    // MARK: - Convenience Accessors

    var briefingEnabled: Bool {
        briefing["enabled"]?.boolVal ?? false
    }

    var briefingTime: String {
        briefing["time"]?.stringValue ?? "08:00"
    }

    var quietHoursEnabled: Bool {
        quietHours["enabled"]?.boolVal ?? false
    }

    var quietHoursStart: String {
        quietHours["start"]?.stringValue ?? "22:00"
    }

    var quietHoursEnd: String {
        quietHours["end"]?.stringValue ?? "08:00"
    }

    var patternDetectionEnabled: Bool {
        patterns["enabled"]?.boolVal ?? false
    }

    var patternCount: Int {
        patterns["count"]?.intVal ?? 0
    }

    var weatherEnabled: Bool {
        weather["enabled"]?.boolVal ?? false
    }

    var weatherLocation: String {
        weather["location"]?.stringValue ?? ""
    }
}

/// Mirrors backend PolicyUpdateRequest.
struct ProactivePolicyUpdateRequest: Codable {
    var interruptionPolicy: String?
    var briefingEnabled: Bool?
    var briefingTime: String?
    var quietHoursEnabled: Bool?
    var quietHoursStart: String?
    var quietHoursEnd: String?
    var patternDetectionEnabled: Bool?
    var weatherEnabled: Bool?
    var weatherLocation: String?

    enum CodingKeys: String, CodingKey {
        case interruptionPolicy = "interruption_policy"
        case briefingEnabled = "briefing_enabled"
        case briefingTime = "briefing_time"
        case quietHoursEnabled = "quiet_hours_enabled"
        case quietHoursStart = "quiet_hours_start"
        case quietHoursEnd = "quiet_hours_end"
        case patternDetectionEnabled = "pattern_detection_enabled"
        case weatherEnabled = "weather_enabled"
        case weatherLocation = "weather_location"
    }
}

/// Mirrors backend PatternResponse — only stores counts (not full pattern dicts).
struct ProactivePatternResponse: Codable {
    let totalCount: Int
    let validCount: Int
    let lastAnalysis: String?

    enum CodingKeys: String, CodingKey {
        case totalCount = "total_count"
        case validCount = "valid_count"
        case lastAnalysis = "last_analysis"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalCount = try container.decode(Int.self, forKey: .totalCount)
        validCount = try container.decode(Int.self, forKey: .validCount)
        lastAnalysis = try container.decodeIfPresent(String.self, forKey: .lastAnalysis)
        // Skip "patterns" array — not needed in settings UI
    }
}

// MARK: - AnyCodableValue Convenience (extends type from APIModels.swift)

extension AnyCodableValue {
    var boolVal: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }

    var intVal: Int? {
        switch self {
        case .int(let i): return i
        case .double(let d): return Int(d)
        default: return nil
        }
    }
}
