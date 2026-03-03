import Foundation

// MARK: - Health Data API Types (macOS)

/// Mirrors the backend HealthSummaryResponse.
/// Categories: activity, heart, sleep, body, nutrition, mindfulness.
struct MacHealthSummaryResponse: Codable {
    let date: String
    let activity: [String: AnyCodableValue]
    let heart: [String: AnyCodableValue]
    let sleep: [String: AnyCodableValue]
    let body: [String: AnyCodableValue]
    let nutrition: [String: AnyCodableValue]
    let mindfulness: [String: AnyCodableValue]

    /// Helper to extract a Double from a category dict
    func double(from category: [String: AnyCodableValue], key: String) -> Double? {
        guard let val = category[key] else { return nil }
        switch val {
        case .double(let d): return d
        case .int(let i): return Double(i)
        case .string(let s): return Double(s)
        default: return nil
        }
    }
}

/// Mirrors the backend HealthTrendResponse.
struct MacHealthTrendResponse: Codable {
    let metricType: String
    let days: Int
    let dataPoints: [MacHealthTrendPoint]
    let trend: String
    let average: Double?
    let minValue: Double?
    let maxValue: Double?

    enum CodingKeys: String, CodingKey {
        case metricType = "metric_type"
        case days
        case dataPoints = "data_points"
        case trend, average
        case minValue = "min_value"
        case maxValue = "max_value"
    }
}

struct MacHealthTrendPoint: Codable {
    let date: String
    let value: Double?
    let count: Int?
}

// MARK: - AnyCodableValue
// Required for macOS target — shared definition lives in Shared/Models/APIModels.swift (iOS)

enum AnyCodableValue: Codable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(Bool.self) { self = .bool(v); return }
        if let v = try? container.decode(Int.self) { self = .int(v); return }
        if let v = try? container.decode(Double.self) { self = .double(v); return }
        if let v = try? container.decode(String.self) { self = .string(v); return }
        if container.decodeNil() { self = .null; return }
        throw DecodingError.typeMismatch(AnyCodableValue.self, .init(codingPath: decoder.codingPath, debugDescription: "Unsupported type"))
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let v): try container.encode(v)
        case .int(let v): try container.encode(v)
        case .double(let v): try container.encode(v)
        case .bool(let v): try container.encode(v)
        case .null: try container.encodeNil()
        }
    }

    var doubleValue: Double? {
        switch self {
        case .double(let d): return d
        case .int(let i): return Double(i)
        case .string(let s): return Double(s)
        default: return nil
        }
    }
}
