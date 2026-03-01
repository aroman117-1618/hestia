import Foundation
import SwiftUI
import HestiaShared

// MARK: - Newsfeed Item Type

enum NewsfeedItemType: String, Codable, CaseIterable {
    case orderExecution = "order_execution"
    case memoryReview = "memory_review"
    case taskUpdate = "task_update"
    case healthInsight = "health_insight"
    case calendarEvent = "calendar_event"
    case systemAlert = "system_alert"

    var displayName: String {
        switch self {
        case .orderExecution: return "Orders"
        case .memoryReview: return "Memory"
        case .taskUpdate: return "Tasks"
        case .healthInsight: return "Health"
        case .calendarEvent: return "Calendar"
        case .systemAlert: return "System"
        }
    }

    var iconName: String {
        switch self {
        case .orderExecution: return "clock.arrow.circlepath"
        case .memoryReview: return "brain"
        case .taskUpdate: return "checklist"
        case .healthInsight: return "heart.fill"
        case .calendarEvent: return "calendar"
        case .systemAlert: return "exclamationmark.triangle"
        }
    }

    var accentColor: Color {
        switch self {
        case .orderExecution: return Color(hex: "007AFF")
        case .memoryReview: return Color(hex: "AF52DE")
        case .taskUpdate: return Color(hex: "FF9500")
        case .healthInsight: return Color(hex: "FF2D55")
        case .calendarEvent: return Color(hex: "34C759")
        case .systemAlert: return Color(hex: "FF3B30")
        }
    }
}

// MARK: - Newsfeed Item Source

enum NewsfeedItemSource: String, Codable, CaseIterable {
    case orders
    case memory
    case tasks
    case health
    case calendar
    case system
}

// MARK: - Newsfeed Item Priority

enum NewsfeedItemPriority: String, Codable {
    case low
    case normal
    case high
    case urgent
}

// MARK: - Newsfeed Item

struct NewsfeedItem: Codable, Identifiable {
    let id: String
    let itemType: String
    let source: String
    let title: String
    let body: String?
    let timestamp: String
    let priority: String
    let icon: String?
    let color: String?
    let actionType: String?
    let actionId: String?
    let metadata: [String: AnyCodableValue]?
    let isRead: Bool
    let isDismissed: Bool

    var type: NewsfeedItemType {
        NewsfeedItemType(rawValue: itemType) ?? .systemAlert
    }

    var itemSource: NewsfeedItemSource {
        NewsfeedItemSource(rawValue: source) ?? .system
    }

    var itemPriority: NewsfeedItemPriority {
        NewsfeedItemPriority(rawValue: priority) ?? .normal
    }

    var parsedTimestamp: Date? {
        ISO8601DateFormatter().date(from: timestamp)
    }

    var relativeTime: String {
        guard let date = parsedTimestamp else { return "" }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    var displayIcon: String {
        icon ?? type.iconName
    }

    var displayColor: Color {
        if let hex = color {
            return Color(hex: hex)
        }
        return type.accentColor
    }
}

// MARK: - API Response Models

struct NewsfeedTimelineResponse: Codable {
    let items: [NewsfeedItem]
    let count: Int
    let unreadCount: Int
}

struct NewsfeedUnreadResponse: Codable {
    let total: Int
    let byType: [String: Int]
}

struct NewsfeedActionResponse: Codable {
    let success: Bool
    let itemId: String
}

struct NewsfeedRefreshResponse: Codable {
    let itemsRefreshed: Int
}
