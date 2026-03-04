import Foundation

// MARK: - Inbox API Response Models

struct InboxItemResponse: Codable, Identifiable {
    let id: String
    let itemType: String
    let source: String
    let title: String
    let body: String?
    let timestamp: String?
    let priority: String
    let sender: String?
    let senderDetail: String?
    let hasAttachments: Bool
    let icon: String?
    let color: String?
    let metadata: [String: AnyCodableValue]
    let isRead: Bool
    let isArchived: Bool

    enum CodingKeys: String, CodingKey {
        case id, title, body, timestamp, priority, sender, icon, color, metadata
        case itemType = "item_type"
        case source
        case senderDetail = "sender_detail"
        case hasAttachments = "has_attachments"
        case isRead = "is_read"
        case isArchived = "is_archived"
    }

    /// Relative time string for display (e.g. "2h ago", "Yesterday")
    var relativeTime: String {
        guard let timestamp = timestamp else { return "" }
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: timestamp) {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        // Fallback: try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: timestamp) {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        return timestamp
    }

    /// Full formatted date for detail view
    var formattedDate: String {
        guard let timestamp = timestamp else { return "" }
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = isoFormatter.date(from: timestamp)
        if date == nil {
            isoFormatter.formatOptions = [.withInternetDateTime]
            date = isoFormatter.date(from: timestamp)
        }
        guard let parsed = date else { return timestamp }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: parsed)
    }

    /// Extract metadata string value by key
    func metadataString(_ key: String) -> String? {
        guard let val = metadata[key] else { return nil }
        switch val {
        case .string(let s): return s
        default: return nil
        }
    }
}

struct InboxListResponse: Codable {
    let items: [InboxItemResponse]
    let total: Int
}

struct InboxUnreadResponse: Codable {
    let total: Int
    let bySource: [String: Int]

    enum CodingKeys: String, CodingKey {
        case total
        case bySource = "by_source"
    }
}

struct InboxMarkAllReadResponse: Codable {
    let markedCount: Int

    enum CodingKeys: String, CodingKey {
        case markedCount = "marked_count"
    }
}

struct InboxRefreshResponse: Codable {
    let refreshed: Int
}
