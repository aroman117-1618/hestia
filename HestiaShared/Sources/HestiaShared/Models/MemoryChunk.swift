import Foundation

/// A memory chunk from the Hestia memory system
public struct MemoryChunk: Codable, Identifiable, Sendable {
    public let id: String
    public let sessionId: String
    public let timestamp: Date
    public let content: String
    public let chunkType: ChunkType
    public let scope: MemoryScope
    public let status: MemoryStatus
    public let tags: ChunkTags
    public let metadata: ChunkMetadata

    public init(id: String, sessionId: String, timestamp: Date, content: String, chunkType: ChunkType, scope: MemoryScope, status: MemoryStatus, tags: ChunkTags, metadata: ChunkMetadata) {
        self.id = id
        self.sessionId = sessionId
        self.timestamp = timestamp
        self.content = content
        self.chunkType = chunkType
        self.scope = scope
        self.status = status
        self.tags = tags
        self.metadata = metadata
    }

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
public enum ChunkType: String, Codable, Sendable {
    case conversation
    case fact
    case preference
    case decision
    case actionItem = "action_item"
    case research
    case system
}

/// Scope of memory retention
public enum MemoryScope: String, Codable, Sendable {
    case session
    case shortTerm = "short_term"
    case longTerm = "long_term"
}

/// Status of a memory chunk
public enum MemoryStatus: String, Codable, Sendable {
    case active
    case staged      // Awaiting human review
    case committed   // Approved for long-term
    case superseded  // Replaced by newer info
    case archived
}

/// Tag-based metadata for memory chunks
public struct ChunkTags: Codable, Sendable {
    public let topics: [String]
    public let entities: [String]
    public let people: [String]
    public let mode: String?
    public let phase: String?
    public let status: [String]
    public let custom: [String: String]

    public init(topics: [String], entities: [String], people: [String], mode: String?, phase: String?, status: [String], custom: [String: String]) {
        self.topics = topics
        self.entities = entities
        self.people = people
        self.mode = mode
        self.phase = phase
        self.status = status
        self.custom = custom
    }
}

/// Additional metadata about a memory chunk
public struct ChunkMetadata: Codable, Sendable {
    public let hasCode: Bool
    public let hasDecision: Bool
    public let hasActionItem: Bool
    public let sentiment: String?
    public let confidence: Double
    public let tokenCount: Int
    public let source: String?

    public init(hasCode: Bool, hasDecision: Bool, hasActionItem: Bool, sentiment: String?, confidence: Double, tokenCount: Int, source: String?) {
        self.hasCode = hasCode
        self.hasDecision = hasDecision
        self.hasActionItem = hasActionItem
        self.sentiment = sentiment
        self.confidence = confidence
        self.tokenCount = tokenCount
        self.source = source
    }

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
public struct MemorySearchResult: Codable, Identifiable, Sendable {
    public let chunk: MemoryChunk
    public let relevanceScore: Double
    public let matchType: String

    public var id: String { chunk.id }

    public init(chunk: MemoryChunk, relevanceScore: Double, matchType: String) {
        self.chunk = chunk
        self.relevanceScore = relevanceScore
        self.matchType = matchType
    }

    enum CodingKeys: String, CodingKey {
        case chunk
        case relevanceScore = "relevance_score"
        case matchType = "match_type"
    }
}

/// Staged memory update pending review
public struct StagedMemoryUpdate: Codable, Identifiable, Sendable {
    public let id: String
    public let chunkId: String
    public let stagedAt: Date
    public let reviewStatus: ReviewStatus
    public let chunk: MemoryChunk

    public init(id: String, chunkId: String, stagedAt: Date, reviewStatus: ReviewStatus, chunk: MemoryChunk) {
        self.id = id
        self.chunkId = chunkId
        self.stagedAt = stagedAt
        self.reviewStatus = reviewStatus
        self.chunk = chunk
    }

    enum CodingKeys: String, CodingKey {
        case id
        case chunkId = "chunk_id"
        case stagedAt = "staged_at"
        case reviewStatus = "review_status"
        case chunk
    }
}

/// Review status for staged memory
public enum ReviewStatus: String, Codable, Sendable {
    case pending
    case approved
    case rejected
}

// MARK: - Mock Data

extension MemorySearchResult {
    /// Mock search results for Neural Net graph visualization (diverse types + overlapping tags)
    public static let mockResults: [MemorySearchResult] = {
        let chunks: [(String, String, ChunkType, [String], [String], Double)] = [
            ("mem-001", "User prefers dark mode across all applications", .preference, ["ui", "preferences"], ["dark mode"], 0.95),
            ("mem-002", "Hestia uses Qwen 2.5 7B as primary local model", .fact, ["infrastructure", "AI"], ["Qwen", "Ollama"], 0.92),
            ("mem-003", "Decided to use FastAPI for the backend REST API", .decision, ["infrastructure", "architecture"], ["FastAPI", "Python"], 0.88),
            ("mem-004", "User works ~6 hours per week on Hestia", .fact, ["schedule", "preferences"], ["andrew"], 0.85),
            ("mem-005", "Cloud routing uses 3-state model: disabled, smart, full", .fact, ["infrastructure", "AI"], ["cloud", "routing"], 0.90),
            ("mem-006", "Implement temporal decay for memory relevance scoring", .decision, ["AI", "architecture"], ["memory", "decay"], 0.87),
            ("mem-007", "User prefers teach-as-we-build approach (70/30 split)", .preference, ["preferences", "communication"], ["andrew"], 0.91),
            ("mem-008", "Security: double encryption with Fernet + Keychain AES-256", .fact, ["security", "infrastructure"], ["encryption", "Keychain"], 0.93),
            ("mem-009", "Review council architecture for performance optimization", .actionItem, ["AI", "architecture"], ["council", "performance"], 0.72),
            ("mem-010", "SwiftUI app targets iOS 26.0 with ObservableObject pattern", .fact, ["ui", "infrastructure"], ["SwiftUI", "iOS"], 0.89),
            ("mem-011", "User prefers sardonic, competent AI personality", .preference, ["preferences", "communication"], ["personality"], 0.94),
            ("mem-012", "Biometric auth via Face ID with Keychain token storage", .fact, ["security", "infrastructure"], ["Face ID", "Keychain"], 0.91),
        ]

        return chunks.map { (id, content, type, topics, entities, confidence) in
            MemorySearchResult(
                chunk: MemoryChunk(
                    id: id,
                    sessionId: "session-mock",
                    timestamp: Date().addingTimeInterval(-Double.random(in: 3600...604800)),
                    content: content,
                    chunkType: type,
                    scope: .longTerm,
                    status: .committed,
                    tags: ChunkTags(
                        topics: topics,
                        entities: entities,
                        people: topics.contains("preferences") ? ["andrew"] : [],
                        mode: "tia",
                        phase: nil,
                        status: ["active"],
                        custom: [:]
                    ),
                    metadata: ChunkMetadata(
                        hasCode: false,
                        hasDecision: type == .decision,
                        hasActionItem: type == .actionItem,
                        sentiment: "neutral",
                        confidence: confidence,
                        tokenCount: content.count / 4,
                        source: "conversation"
                    )
                ),
                relevanceScore: confidence,
                matchType: "semantic"
            )
        }
    }()
}

extension MemoryChunk {
    public static let mockPendingReviews: [MemoryChunk] = [
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
