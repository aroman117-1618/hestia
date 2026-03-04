import Foundation
import HestiaShared

private struct FilesEmptyBody: Codable {}

// MARK: - Files API Extensions

extension APIClient {
    /// List directory contents from the server.
    func listFiles(path: String, showHidden: Bool = false, sortBy: String = "name", limit: Int = 100, offset: Int = 0) async throws -> FileListResponse {
        let encodedPath = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return try await get("../v1/files?path=\(encodedPath)&show_hidden=\(showHidden)&sort_by=\(sortBy)&limit=\(limit)&offset=\(offset)")
    }

    /// Read text file content from the server.
    func readFileContent(path: String) async throws -> FileTextContentResponse {
        let encodedPath = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return try await get("../v1/files/content?path=\(encodedPath)")
    }

    /// Get file or directory metadata.
    func getFileMetadata(path: String) async throws -> FileEntryResponse {
        let encodedPath = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return try await get("../v1/files/metadata?path=\(encodedPath)")
    }

    /// Create a new file or directory.
    func createFile(parentPath: String, name: String, content: String? = nil, type: String = "file") async throws -> FileEntryResponse {
        let body = FileCreateRequest(path: parentPath, name: name, content: content, type: type)
        return try await post("../v1/files", body: body)
    }

    /// Update file content (text files only).
    func updateFileContent(path: String, content: String) async throws -> FileEntryResponse {
        let encodedPath = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return try await put("../v1/files?path=\(encodedPath)", body: FileUpdateRequest(content: content))
    }

    /// Delete file (soft delete to trash). Uses POST because APIClient.delete() is private.
    func deleteFile(path: String) async throws -> FileDeleteResponse {
        let encodedPath = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return try await post("../v1/files/delete?path=\(encodedPath)", body: FilesEmptyBody())
    }

    /// Move or rename a file.
    func moveFile(source: String, destination: String) async throws -> FileEntryResponse {
        return try await put("../v1/files/move", body: FileMoveRequest(source: source, destination: destination))
    }

    /// Get file operation audit log.
    func getFileAuditLog(limit: Int = 100, offset: Int = 0) async throws -> AuditLogListResponse {
        return try await get("../v1/files/audit-log?limit=\(limit)&offset=\(offset)")
    }
}
