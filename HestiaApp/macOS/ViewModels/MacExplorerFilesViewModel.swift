import SwiftUI
import HestiaShared

// MARK: - Path Segment for Breadcrumbs

struct PathSegment: Identifiable {
    let id = UUID()
    let name: String
    let fullPath: String
}

// MARK: - Sort Options

enum FileSortOption: String, CaseIterable {
    case name = "name"
    case modified = "modified"
    case size = "size"
    case type = "type"

    var label: String {
        switch self {
        case .name: return "Name"
        case .modified: return "Modified"
        case .size: return "Size"
        case .type: return "Type"
        }
    }
}

// MARK: - Files ViewModel (API-backed)

@MainActor
class MacExplorerFilesViewModel: ObservableObject {
    // MARK: - Published State

    @Published var currentPath: String = "~/Documents"
    @Published var files: [FileEntryResponse] = []
    @Published var parentPath: String?
    @Published var selectedFile: FileEntryResponse?
    @Published var fileContent: String?
    @Published var isLoading: Bool = false
    @Published var isLoadingContent: Bool = false
    @Published var error: String?
    @Published var searchText: String = ""
    @Published var sortBy: FileSortOption = .name
    @Published var showHidden: Bool = false
    @Published var isEditing: Bool = false
    @Published var editContent: String = ""

    // MARK: - Create / Rename State

    @Published var showingCreateFile: Bool = false
    @Published var showingCreateFolder: Bool = false
    @Published var showingRename: Bool = false
    @Published var newItemName: String = ""
    @Published var showingDeleteConfirm: Bool = false
    @Published var fileToDelete: FileEntryResponse?

    // MARK: - Computed Properties

    var breadcrumbs: [PathSegment] {
        parseBreadcrumbs(from: currentPath)
    }

    var filteredFiles: [FileEntryResponse] {
        guard !searchText.isEmpty else { return files }
        return files.filter { $0.name.localizedCaseInsensitiveContains(searchText) }
    }

    var hasFiles: Bool { !files.isEmpty }
    var hasError: Bool { error != nil }

    // MARK: - Directory Loading

    func loadDirectory(_ path: String? = nil) {
        let targetPath = path ?? currentPath
        isLoading = true
        error = nil

        Task { [weak self] in
            guard let self else { return }
            do {
                let response = try await APIClient.shared.listFiles(
                    path: targetPath,
                    showHidden: self.showHidden,
                    sortBy: self.sortBy.rawValue
                )
                self.currentPath = response.path
                self.parentPath = response.parentPath
                self.files = response.files
                self.isLoading = false
                #if DEBUG
                print("[ExplorerFiles] Loaded \(response.files.count) items at \(response.path)")
                #endif
            } catch {
                self.isLoading = false
                self.error = "Failed to load directory"
                #if DEBUG
                print("[ExplorerFiles] Error loading directory: \(error)")
                #endif
            }
        }
    }

    func navigateToDirectory(_ path: String) {
        selectedFile = nil
        fileContent = nil
        isEditing = false
        loadDirectory(path)
    }

    func navigateUp() {
        guard let parent = parentPath else { return }
        navigateToDirectory(parent)
    }

    func refresh() {
        loadDirectory(currentPath)
    }

    // MARK: - File Selection & Content

    func selectFile(_ file: FileEntryResponse) {
        if file.isDirectory {
            navigateToDirectory(file.path)
            return
        }

        selectedFile = file
        isEditing = false

        if file.isTextFile {
            loadFileContent(file)
        } else {
            fileContent = nil
        }
    }

    private func loadFileContent(_ file: FileEntryResponse) {
        isLoadingContent = true
        fileContent = nil

        Task { [weak self] in
            guard let self else { return }
            do {
                let response = try await APIClient.shared.readFileContent(path: file.path)
                self.fileContent = response.content
                self.isLoadingContent = false
            } catch {
                self.fileContent = nil
                self.isLoadingContent = false
                #if DEBUG
                print("[ExplorerFiles] Error loading content: \(error)")
                #endif
            }
        }
    }

    // MARK: - Editing

    func startEditing() {
        guard let content = fileContent else { return }
        editContent = content
        isEditing = true
    }

    func cancelEditing() {
        isEditing = false
        editContent = ""
    }

    func saveEdit() {
        guard let file = selectedFile, isEditing else { return }
        let content = editContent

        Task { [weak self] in
            guard let self else { return }
            do {
                _ = try await APIClient.shared.updateFileContent(path: file.path, content: content)
                self.fileContent = content
                self.isEditing = false
                self.editContent = ""
                #if DEBUG
                print("[ExplorerFiles] Saved \(file.name)")
                #endif
            } catch {
                self.error = "Failed to save file"
                #if DEBUG
                print("[ExplorerFiles] Error saving: \(error)")
                #endif
            }
        }
    }

    // MARK: - CRUD Operations

    func createFile(name: String, content: String? = nil, type: String = "file") {
        guard !name.isEmpty else { return }

        Task { [weak self] in
            guard let self else { return }
            do {
                _ = try await APIClient.shared.createFile(
                    parentPath: self.currentPath,
                    name: name,
                    content: content,
                    type: type
                )
                self.loadDirectory()
                #if DEBUG
                print("[ExplorerFiles] Created \(type): \(name)")
                #endif
            } catch {
                self.error = "Failed to create \(type)"
                #if DEBUG
                print("[ExplorerFiles] Error creating \(type): \(error)")
                #endif
            }
        }
    }

    func deleteFile(_ file: FileEntryResponse) {
        Task { [weak self] in
            guard let self else { return }
            do {
                _ = try await APIClient.shared.deleteFile(path: file.path)
                if self.selectedFile?.path == file.path {
                    self.selectedFile = nil
                    self.fileContent = nil
                }
                self.loadDirectory()
                #if DEBUG
                print("[ExplorerFiles] Deleted \(file.name)")
                #endif
            } catch {
                self.error = "Failed to delete file"
                #if DEBUG
                print("[ExplorerFiles] Error deleting: \(error)")
                #endif
            }
        }
    }

    func renameFile(_ file: FileEntryResponse, newName: String) {
        guard !newName.isEmpty, newName != file.name else { return }

        // Compute destination: same directory, new name
        let parentDir: String
        if let lastSlash = file.path.lastIndex(of: "/") {
            parentDir = String(file.path[..<lastSlash])
        } else {
            parentDir = currentPath
        }
        let destination = parentDir + "/" + newName

        Task { [weak self] in
            guard let self else { return }
            do {
                _ = try await APIClient.shared.moveFile(source: file.path, destination: destination)
                self.loadDirectory()
                #if DEBUG
                print("[ExplorerFiles] Renamed \(file.name) -> \(newName)")
                #endif
            } catch {
                self.error = "Failed to rename file"
                #if DEBUG
                print("[ExplorerFiles] Error renaming: \(error)")
                #endif
            }
        }
    }

    func openInFinder(_ file: FileEntryResponse) {
        let expandedPath = file.path.replacingOccurrences(of: "~", with: NSHomeDirectory())
        let url = URL(fileURLWithPath: expandedPath)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    // MARK: - Breadcrumb Parsing

    private func parseBreadcrumbs(from path: String) -> [PathSegment] {
        var segments: [PathSegment] = []
        let cleanPath = path.hasPrefix("~/") ? path : path

        // Split on "/"
        let parts: [String]
        if cleanPath.hasPrefix("~/") {
            parts = ["~"] + cleanPath.dropFirst(2).split(separator: "/").map(String.init)
        } else if cleanPath.hasPrefix("/") {
            parts = ["/"] + cleanPath.dropFirst().split(separator: "/").map(String.init)
        } else {
            parts = cleanPath.split(separator: "/").map(String.init)
        }

        for (index, part) in parts.enumerated() {
            let fullPath: String
            if index == 0 && part == "~" {
                fullPath = "~"
            } else if index == 0 && part == "/" {
                fullPath = "/"
            } else {
                // Reconstruct path up to this segment
                let prefix = parts[0] == "~" ? "~/" : parts[0] == "/" ? "/" : ""
                let middle = parts[1...index].joined(separator: "/")
                fullPath = prefix + middle
            }
            segments.append(PathSegment(name: part, fullPath: fullPath))
        }

        return segments
    }
}
