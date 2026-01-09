import Foundation

/// A scheduled, recurring prompt that Hestia executes autonomously
struct Order: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String
    var prompt: String
    var scheduledTime: Date
    var frequency: OrderFrequency
    var resources: Set<MCPResource>
    var orderStatus: OrderStatus
    var lastExecution: OrderExecution?
    let createdAt: Date
    var updatedAt: Date

    // MARK: - Validation

    /// Validates the order meets all requirements
    var isValid: Bool {
        prompt.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10 &&
        !resources.isEmpty &&
        frequency.isValid
    }

    /// Returns validation errors if any
    var validationErrors: [String] {
        var errors: [String] = []

        if prompt.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 {
            errors.append("Prompt must be at least 10 characters")
        }

        if resources.isEmpty {
            errors.append("At least one resource must be selected")
        }

        if !frequency.isValid {
            errors.append("Custom frequency must be at least 15 minutes")
        }

        return errors
    }
}

// MARK: - Order Frequency

enum OrderFrequency: Codable, Equatable {
    case once
    case daily
    case weekly
    case monthly
    case custom(minutes: Int)

    var displayName: String {
        switch self {
        case .once: return "Once"
        case .daily: return "Daily"
        case .weekly: return "Weekly"
        case .monthly: return "Monthly"
        case .custom(let minutes):
            if minutes < 60 {
                return "Every \(minutes) minutes"
            } else if minutes == 60 {
                return "Hourly"
            } else {
                let hours = minutes / 60
                return "Every \(hours) hours"
            }
        }
    }

    var isValid: Bool {
        switch self {
        case .custom(let minutes):
            return minutes >= 15
        default:
            return true
        }
    }

    var typeString: String {
        switch self {
        case .once: return "once"
        case .daily: return "daily"
        case .weekly: return "weekly"
        case .monthly: return "monthly"
        case .custom: return "custom"
        }
    }

    var customMinutes: Int? {
        if case .custom(let minutes) = self {
            return minutes
        }
        return nil
    }

    static func from(type: String, customMinutes: Int) -> OrderFrequency {
        switch type {
        case "once": return .once
        case "daily": return .daily
        case "weekly": return .weekly
        case "monthly": return .monthly
        case "custom": return .custom(minutes: max(15, customMinutes))
        default: return .once
        }
    }

    // MARK: - Codable

    enum CodingKeys: String, CodingKey {
        case type
        case minutes
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)

        switch type {
        case "once": self = .once
        case "daily": self = .daily
        case "weekly": self = .weekly
        case "monthly": self = .monthly
        case "custom":
            let minutes = try container.decode(Int.self, forKey: .minutes)
            self = .custom(minutes: minutes)
        default:
            self = .once
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(typeString, forKey: .type)
        if case .custom(let minutes) = self {
            try container.encode(minutes, forKey: .minutes)
        }
    }
}

// MARK: - Order Status

enum OrderStatus: String, Codable, CaseIterable {
    case active
    case inactive

    var displayName: String {
        switch self {
        case .active: return "Active"
        case .inactive: return "Paused"
        }
    }

    var iconName: String {
        switch self {
        case .active: return "checkmark.circle.fill"
        case .inactive: return "pause.circle.fill"
        }
    }
}

// MARK: - Execution Status

enum ExecutionStatus: String, Codable, CaseIterable {
    case scheduled
    case running
    case success
    case failed

    var displayName: String {
        switch self {
        case .scheduled: return "Scheduled"
        case .running: return "Running"
        case .success: return "Completed"
        case .failed: return "Failed"
        }
    }

    var iconName: String {
        switch self {
        case .scheduled: return "clock"
        case .running: return "arrow.triangle.2.circlepath"
        case .success: return "checkmark.circle.fill"
        case .failed: return "exclamationmark.triangle.fill"
        }
    }
}

// MARK: - Order Execution

struct OrderExecution: Identifiable, Codable, Equatable {
    let id: UUID
    let orderId: UUID
    let timestamp: Date
    let status: ExecutionStatus
    let hestiaRead: String?
    let fullResponse: String?

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter.string(from: timestamp)
    }
}

// MARK: - MCP Resources

enum MCPResource: String, Codable, CaseIterable, Identifiable {
    case firecrawl = "firecrawl"
    case github = "github"
    case appleNews = "apple_news"
    case fidelity = "fidelity"
    case calendar = "calendar"
    case email = "email"
    case reminder = "reminder"
    case note = "note"
    case shortcut = "shortcut"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .firecrawl: return "Firecrawl/Websearch"
        case .github: return "Github"
        case .appleNews: return "News (Apple)"
        case .fidelity: return "Fidelity"
        case .calendar: return "Calendar"
        case .email: return "Email"
        case .reminder: return "Reminder"
        case .note: return "Note"
        case .shortcut: return "Shortcut"
        }
    }

    var iconName: String {
        switch self {
        case .firecrawl: return "globe"
        case .github: return "chevron.left.forwardslash.chevron.right"
        case .appleNews: return "newspaper"
        case .fidelity: return "chart.line.uptrend.xyaxis"
        case .calendar: return "calendar"
        case .email: return "envelope"
        case .reminder: return "checklist"
        case .note: return "note.text"
        case .shortcut: return "square.stack.3d.up"
        }
    }
}

// MARK: - Mock Data

extension Order {
    static let mockOrders: [Order] = [
        Order(
            id: UUID(),
            name: "Morning Brief",
            prompt: "Summarize today's calendar, important emails, and any breaking news relevant to my interests.",
            scheduledTime: Calendar.current.date(bySettingHour: 7, minute: 30, second: 0, of: Date()) ?? Date(),
            frequency: .daily,
            resources: [.calendar, .email, .firecrawl],
            orderStatus: .active,
            lastExecution: OrderExecution(
                id: UUID(),
                orderId: UUID(),
                timestamp: Date().addingTimeInterval(-3600),
                status: .success,
                hestiaRead: nil,
                fullResponse: nil
            ),
            createdAt: Date().addingTimeInterval(-86400 * 7),
            updatedAt: Date()
        ),
        Order(
            id: UUID(),
            name: "Market Watch",
            prompt: "Check my Fidelity portfolio performance and alert me to any significant changes in my watchlist stocks.",
            scheduledTime: Calendar.current.date(bySettingHour: 9, minute: 0, second: 0, of: Date()) ?? Date(),
            frequency: .custom(minutes: 60),
            resources: [.fidelity],
            orderStatus: .active,
            lastExecution: nil,
            createdAt: Date().addingTimeInterval(-86400 * 3),
            updatedAt: Date()
        ),
        Order(
            id: UUID(),
            name: "Research Summary",
            prompt: "Search for recent developments in AI and summarize the top 3 most relevant articles.",
            scheduledTime: Calendar.current.date(bySettingHour: 18, minute: 0, second: 0, of: Date()) ?? Date(),
            frequency: .weekly,
            resources: [.firecrawl, .note],
            orderStatus: .inactive,
            lastExecution: OrderExecution(
                id: UUID(),
                orderId: UUID(),
                timestamp: Date().addingTimeInterval(-86400),
                status: .failed,
                hestiaRead: "Unable to connect to Firecrawl service",
                fullResponse: nil
            ),
            createdAt: Date().addingTimeInterval(-86400 * 14),
            updatedAt: Date().addingTimeInterval(-86400)
        )
    ]
}
