import Foundation

// MARK: - Memory Browser API Response Types

struct MemoryChunkUpdateRequest: Codable {
    let content: String?
    let chunkType: String?
    let tags: [String]?
    // APIClient uses convertToSnakeCase; chunkType encodes as chunk_type automatically.
}

struct MemoryChunkListResponse: Codable {
    let chunks: [MemoryChunkItem]
    let total: Int
    let limit: Int
    let offset: Int
}

struct MemoryChunkItem: Codable, Identifiable, Equatable {
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
    // No explicit CodingKeys — APIClient uses convertFromSnakeCase,
    // which automatically maps chunk_type→chunkType, created_at→createdAt, etc.
    // Explicit snake_case CodingKeys conflict with that strategy and cause silent decode failures.
}
