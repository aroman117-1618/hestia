import Foundation

// MARK: - Memory Browser API Response Types

struct MemoryChunkUpdateRequest: Codable {
    let content: String?
    let chunkType: String?
    let tags: [String]?

    enum CodingKeys: String, CodingKey {
        case content
        case chunkType = "chunk_type"
        case tags
    }
}

struct MemoryChunkListResponse: Codable {
    let chunks: [MemoryChunkItem]
    let total: Int
    let limit: Int
    let offset: Int
}

struct MemoryChunkItem: Codable, Identifiable {
    let id: String
    let content: String
    let chunkType: String
    let importance: Double
    let status: String
    let source: String?
    let topics: [String]
    let entities: [String]
    let createdAt: String
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, content, importance, status, source, topics, entities
        case chunkType = "chunk_type"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}
