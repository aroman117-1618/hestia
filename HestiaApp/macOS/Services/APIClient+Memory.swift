import Foundation
import HestiaShared

/// Memory Browser API methods for macOS target
extension APIClient {
    func listMemoryChunks(
        limit: Int = 50,
        offset: Int = 0,
        sortBy: String = "importance",
        sortOrder: String = "desc",
        chunkType: String? = nil,
        status: String? = nil,
        source: String? = nil
    ) async throws -> MemoryChunkListResponse {
        var path = "/memory/chunks?limit=\(limit)&offset=\(offset)&sort_by=\(sortBy)&sort_order=\(sortOrder)"
        if let ct = chunkType { path += "&chunk_type=\(ct)" }
        if let s = status { path += "&status=\(s)" }
        if let src = source { path += "&source=\(src)" }
        return try await get(path)
    }

    func getChunk(_ id: String) async throws -> MemoryChunkItem {
        return try await get("/memory/chunks/\(id)")
    }

    func updateChunk(_ id: String, request: MemoryChunkUpdateRequest) async throws -> MemoryChunkItem {
        return try await put("/memory/chunks/\(id)", body: request)
    }
}
