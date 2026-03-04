import Foundation
import HestiaShared

private struct InboxEmptyBody: Codable {}

// MARK: - Inbox API Extensions

extension APIClient {
    /// List inbox items, optionally filtered by source or type.
    func getInbox(source: String? = nil, type: String? = nil, includeArchived: Bool = false, limit: Int = 100, offset: Int = 0) async throws -> InboxListResponse {
        var query = "include_archived=\(includeArchived)&limit=\(limit)&offset=\(offset)"
        if let source = source {
            let encoded = source.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? source
            query += "&source=\(encoded)"
        }
        if let type = type {
            let encoded = type.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? type
            query += "&type=\(encoded)"
        }
        return try await get("../v1/inbox?\(query)")
    }

    /// Get unread count, optionally filtered by source.
    func getInboxUnreadCount(source: String? = nil) async throws -> InboxUnreadResponse {
        var query = ""
        if let source = source {
            let encoded = source.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? source
            query = "?source=\(encoded)"
        }
        return try await get("../v1/inbox/unread-count\(query)")
    }

    /// Get a single inbox item by ID.
    func getInboxItem(id: String) async throws -> InboxItemResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? id
        return try await get("../v1/inbox/\(encoded)")
    }

    /// Mark a single inbox item as read.
    func markInboxItemRead(id: String) async throws -> InboxItemResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? id
        return try await post("../v1/inbox/\(encoded)/read", body: InboxEmptyBody())
    }

    /// Mark all inbox items as read, optionally filtered by source.
    func markAllInboxRead(source: String? = nil) async throws -> InboxMarkAllReadResponse {
        var query = ""
        if let source = source {
            let encoded = source.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? source
            query = "?source=\(encoded)"
        }
        return try await post("../v1/inbox/mark-all-read\(query)", body: InboxEmptyBody())
    }

    /// Archive a single inbox item.
    func archiveInboxItem(id: String) async throws -> InboxItemResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? id
        return try await post("../v1/inbox/\(encoded)/archive", body: InboxEmptyBody())
    }

    /// Refresh inbox from all sources.
    func refreshInbox() async throws -> InboxRefreshResponse {
        return try await post("../v1/inbox/refresh", body: InboxEmptyBody())
    }
}
