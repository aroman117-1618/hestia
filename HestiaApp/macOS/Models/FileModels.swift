import Foundation

// MARK: - File API Response Models

struct FileEntryResponse: Codable, Identifiable {
    let name: String
    let path: String
    let type: String  // "file" or "directory"
    let size: Int
    let modified: String
    let mimeType: String?
    let isHidden: Bool
    let extension_: String?

    var id: String { path }

    enum CodingKeys: String, CodingKey {
        case name, path, type, size, modified
        case mimeType = "mime_type"
        case isHidden = "is_hidden"
        case extension_ = "extension"
    }

    var isDirectory: Bool { type == "directory" }

    var icon: String {
        if isDirectory { return "folder.fill" }
        guard let ext = extension_?.lowercased() else { return "doc" }
        switch ext {
        case "md", "markdown": return "doc.richtext"
        case "pdf": return "doc.fill"
        case "swift", "py", "js", "ts": return "chevron.left.forwardslash.chevron.right"
        case "json", "yaml", "yml": return "curlybraces"
        case "png", "jpg", "jpeg", "gif": return "photo"
        case "txt": return "doc.text"
        default: return "doc"
        }
    }

    var formattedSize: String {
        if isDirectory { return "--" }
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(size))
    }

    var formattedDate: String {
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: modified) {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        // Fallback: try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: modified) {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        return modified
    }

    var isTextFile: Bool {
        guard let ext = extension_?.lowercased() else { return false }
        let textExtensions = [
            "md", "markdown", "txt", "swift", "py", "js", "ts", "json",
            "yaml", "yml", "csv", "html", "css", "xml", "sh", "bash",
            "zsh", "toml", "ini", "cfg", "conf", "log", "env", "gitignore",
            "dockerfile", "makefile", "rst", "tex"
        ]
        return textExtensions.contains(ext)
    }

    var isCodeFile: Bool {
        guard let ext = extension_?.lowercased() else { return false }
        let codeExtensions = [
            "swift", "py", "js", "ts", "json", "yaml", "yml",
            "csv", "html", "css", "xml", "sh", "bash", "zsh", "toml"
        ]
        return codeExtensions.contains(ext)
    }
}

struct FileListResponse: Codable {
    let files: [FileEntryResponse]
    let path: String
    let parentPath: String?
    let total: Int

    enum CodingKeys: String, CodingKey {
        case files, path, total
        case parentPath = "parent_path"
    }
}

struct FileTextContentResponse: Codable {
    let content: String
    let mimeType: String
    let size: Int
    let modified: String
    let encoding: String

    enum CodingKeys: String, CodingKey {
        case content, size, modified, encoding
        case mimeType = "mime_type"
    }
}

struct FileCreateRequest: Codable {
    let path: String
    let name: String
    let content: String?
    let type: String
}

struct FileUpdateRequest: Codable {
    let content: String
}

struct FileMoveRequest: Codable {
    let source: String
    let destination: String
}

struct FileDeleteResponse: Codable {
    let deleted: Bool
    let movedToTrash: Bool

    enum CodingKeys: String, CodingKey {
        case deleted
        case movedToTrash = "moved_to_trash"
    }
}

struct AuditLogEntry: Codable, Identifiable {
    let id: String
    let operation: String
    let path: String
    let result: String
    let timestamp: String
    let destinationPath: String?
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case id, operation, path, result, timestamp, metadata
        case destinationPath = "destination_path"
    }
}

struct AuditLogListResponse: Codable {
    let logs: [AuditLogEntry]
    let count: Int
}
