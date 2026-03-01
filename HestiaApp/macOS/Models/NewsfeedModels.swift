import Foundation
import SwiftUI
import HestiaShared

// MARK: - Newsfeed Models (macOS)
// Mirrors iOS NewsfeedModels for the macOS target

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
        icon ?? "doc"
    }

    var displayColor: Color {
        if let hex = color {
            return Color(hex: hex)
        }
        return .blue
    }
}

// MARK: - API Response Types (macOS)

struct NewsfeedTimelineResponse: Codable {
    let items: [NewsfeedItem]
    let count: Int
    let unreadCount: Int
}
