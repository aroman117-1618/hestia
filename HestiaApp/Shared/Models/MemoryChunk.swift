import Foundation

/// A memory chunk from the Hestia memory system
struct MemoryChunk: Codable, Identifiable {
    let id: String
    let sessionId: String
    let timestamp: Date
    let content: String
    let chunkType: ChunkType
    let scope: MemoryScope
    let status: MemoryStatus
    let tags: ChunkTags
    let metadata: ChunkMetadata

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case timestamp
        case content
        case chunkType = "chunk_type"
        case scope
        case status
        case tags
        case metadata
    }
}

/// Type of memory chunk
enum ChunkType: String, Codable {
    case conversation
    case fact
    case preference
    case decision
    case actionItem = "action_item"
    case research
    case system
}

/// Scope of memory retention
enum MemoryScope: String, Codable {
    case session
    case shortTerm = "short_term"
    case longTerm = "long_term"
}

/// Status of a memory chunk
enum MemoryStatus: String, Codable {
    case active
    case staged      // Awaiting human review
    case committed   // Approved for long-term
    case superseded  // Replaced by newer info
    case archived
}

/// Tag-based metadata for memory chunks
struct ChunkTags: Codable {
    let topics: [String]
    let entities: [String]
    let people: [String]
    let mode: String?
    let phase: String?
    let status: [String]
    let custom: [String: String]
}

/// Additional metadata about a memory chunk
struct ChunkMetadata: Codable {
    let hasCode: Bool
    let hasDecision: Bool
    let hasActionItem: Bool
    let sentiment: String?
    let confidence: Double
    let tokenCount: Int
    let source: String?

    enum CodingKeys: String, CodingKey {
        case hasCode = "has_code"
        case hasDecision = "has_decision"
        case hasActionItem = "has_action_item"
        case sentiment
        case confidence
        case tokenCount = "token_count"
        case source
    }
}

// MARK: - Memory Search

/// Result from a memory search
struct MemorySearchResult: Codable, Identifiable {
    let chunk: MemoryChunk
    let relevanceScore: Double
    let matchType: String

    var id: String { chunk.id }

    enum CodingKeys: String, CodingKey {
        case chunk
        case relevanceScore = "relevance_score"
        case matchType = "match_type"
    }
}

/// Staged memory update pending review
struct StagedMemoryUpdate: Codable, Identifiable {
    let id: String
    let chunkId: String
    let stagedAt: Date
    let reviewStatus: ReviewStatus
    let chunk: MemoryChunk

    enum CodingKeys: String, CodingKey {
        case id
        case chunkId = "chunk_id"
        case stagedAt = "staged_at"
        case reviewStatus = "review_status"
        case chunk
    }
}

/// Review status for staged memory
enum ReviewStatus: String, Codable {
    case pending
    case approved
    case rejected
}

// MARK: - Mock Data

extension MemoryChunk {
    static let mockPendingReviews: [MemoryChunk] = [
        MemoryChunk(
            id: "chunk-001",
            sessionId: "session-abc",
            timestamp: Date().addingTimeInterval(-3600),
            content: "User prefers detailed explanations over quick answers when learning new concepts.",
            chunkType: .preference,
            scope: .longTerm,
            status: .staged,
            tags: ChunkTags(
                topics: ["communication", "preferences"],
                entities: [],
                people: ["andrew"],
                mode: "mira",
                phase: nil,
                status: ["pending"],
                custom: [:]
            ),
            metadata: ChunkMetadata(
                hasCode: false,
                hasDecision: false,
                hasActionItem: false,
                sentiment: "neutral",
                confidence: 0.85,
                tokenCount: 45,
                source: "conversation"
            )
        ),
        MemoryChunk(
            id: "chunk-002",
            sessionId: "session-abc",
            timestamp: Date().addingTimeInterval(-7200),
            content: "User works at a tech startup focused on AI-powered productivity tools.",
            chunkType: .fact,
            scope: .longTerm,
            status: .staged,
            tags: ChunkTags(
                topics: ["career", "workplace"],
                entities: ["tech startup", "AI"],
                people: ["andrew"],
                mode: "tia",
                phase: nil,
                status: ["pending"],
                custom: [:]
            ),
            metadata: ChunkMetadata(
                hasCode: false,
                hasDecision: false,
                hasActionItem: false,
                sentiment: "positive",
                confidence: 0.92,
                tokenCount: 38,
                source: "conversation"
            )
        )
    ]
}
