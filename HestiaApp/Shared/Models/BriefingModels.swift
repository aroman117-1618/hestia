import Foundation
import HestiaShared

// MARK: - Briefing Response

struct BriefingResponse: Codable {
    let greeting: String
    let timestamp: String
    let text: String
    let calendar: BriefingCalendar
    let reminders: BriefingReminders
    let tasks: BriefingTasks
    let weather: BriefingWeather
    let suggestions: [String]
    let sections: [BriefingSection]

    var parsedTimestamp: Date? {
        ISO8601DateFormatter().date(from: timestamp)
    }

    var hasCalendarEvents: Bool {
        calendar.count > 0
    }

    var hasReminders: Bool {
        reminders.count > 0
    }
}

// MARK: - Briefing Sub-Types

struct BriefingCalendar: Codable {
    let count: Int
    let events: [BriefingEvent]?
    let summary: String?

    init(from decoder: Decoder) throws {
        // Handle both dict and flexible formats
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.count = (try? container.decode(Int.self, forKey: .count)) ?? 0
        self.events = try? container.decode([BriefingEvent].self, forKey: .events)
        self.summary = try? container.decode(String.self, forKey: .summary)
    }

    private enum CodingKeys: String, CodingKey {
        case count, events, summary
    }
}

struct BriefingEvent: Codable {
    let title: String
    let time: String?
    let location: String?
}

struct BriefingReminders: Codable {
    let count: Int
    let items: [String]?
    let summary: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.count = (try? container.decode(Int.self, forKey: .count)) ?? 0
        self.items = try? container.decode([String].self, forKey: .items)
        self.summary = try? container.decode(String.self, forKey: .summary)
    }

    private enum CodingKeys: String, CodingKey {
        case count, items, summary
    }
}

struct BriefingTasks: Codable {
    let count: Int
    let items: [String]?
    let summary: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.count = (try? container.decode(Int.self, forKey: .count)) ?? 0
        self.items = try? container.decode([String].self, forKey: .items)
        self.summary = try? container.decode(String.self, forKey: .summary)
    }

    private enum CodingKeys: String, CodingKey {
        case count, items, summary
    }
}

struct BriefingWeather: Codable {
    let available: Bool
    let summary: String?
    let temperature: String?
    let condition: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.available = (try? container.decode(Bool.self, forKey: .available)) ?? false
        self.summary = try? container.decode(String.self, forKey: .summary)
        self.temperature = try? container.decode(String.self, forKey: .temperature)
        self.condition = try? container.decode(String.self, forKey: .condition)
    }

    private enum CodingKeys: String, CodingKey {
        case available, summary, temperature, condition
    }
}

struct BriefingSection: Codable {
    let title: String
    let content: String
    let icon: String?
    let priority: String?
}
