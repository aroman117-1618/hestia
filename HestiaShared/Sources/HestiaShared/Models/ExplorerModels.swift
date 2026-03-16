import Foundation

// MARK: - Explorer Resource Models

/// Type of explorer resource
public enum ExplorerResourceType: String, Codable, Sendable, CaseIterable {
    case draft
    case mail
    case task
    case note
    case file
}

/// Source of a resource
public enum ExplorerResourceSource: String, Codable, Sendable, CaseIterable {
    case hestia
    case mail
    case notes
    case reminders
    case files
}

/// Flags on a resource
public enum ExplorerResourceFlag: String, Codable, Sendable {
    case flagged
    case urgent
    case recent
    case plan
    case unread
}

/// A unified resource from the Explorer API
public struct ExplorerResource: Codable, Identifiable, Sendable {
    public let id: String
    public let type: ExplorerResourceType
    public let title: String
    public let source: ExplorerResourceSource
    public let createdAt: String?
    public let modifiedAt: String?
    public let preview: String?
    public let flags: [ExplorerResourceFlag]
    public let color: String?
    public let metadata: [String: String]

    public init(
        id: String,
        type: ExplorerResourceType,
        title: String,
        source: ExplorerResourceSource,
        createdAt: String? = nil,
        modifiedAt: String? = nil,
        preview: String? = nil,
        flags: [ExplorerResourceFlag] = [],
        color: String? = nil,
        metadata: [String: String] = [:]
    ) {
        self.id = id
        self.type = type
        self.title = title
        self.source = source
        self.createdAt = createdAt
        self.modifiedAt = modifiedAt
        self.preview = preview
        self.flags = flags
        self.color = color
        self.metadata = metadata
    }
}

// MARK: - API Response Models

/// Response from GET /v1/explorer/resources
public struct ExplorerResourceListResponse: Codable, Sendable {
    public let resources: [ExplorerResource]
    public let count: Int
}

/// Response from GET /v1/explorer/resources/{id}/content
public struct ExplorerContentResponse: Codable, Sendable {
    public let id: String
    public let content: String?
}

// MARK: - Draft Request Models

/// Request for POST /v1/explorer/drafts
public struct DraftCreateRequest: Codable, Sendable {
    public let title: String
    public let body: String?
    public let color: String?
    public let flags: [String]
    public let metadata: [String: String]

    public init(
        title: String,
        body: String? = nil,
        color: String? = nil,
        flags: [String] = [],
        metadata: [String: String] = [:]
    ) {
        self.title = title
        self.body = body
        self.color = color
        self.flags = flags
        self.metadata = metadata
    }
}

/// Request for PATCH /v1/explorer/drafts/{id}
public struct DraftUpdateRequest: Codable, Sendable {
    public let title: String?
    public let body: String?
    public let color: String?
    public let flags: [String]?
    public let metadata: [String: String]?

    public init(
        title: String? = nil,
        body: String? = nil,
        color: String? = nil,
        flags: [String]? = nil,
        metadata: [String: String]? = nil
    ) {
        self.title = title
        self.body = body
        self.color = color
        self.flags = flags
        self.metadata = metadata
    }
}

/// Response from DELETE /v1/explorer/drafts/{id}
public struct DraftDeleteResponse: Codable, Sendable {
    public let deleted: Bool
}
