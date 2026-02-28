import SwiftUI
import HestiaShared

/// File tree node for the Explorer sidebar.
struct FileNode: Identifiable {
    let id = UUID()
    let name: String
    let path: URL
    let isDirectory: Bool
    var children: [FileNode]?
    var isExpanded: Bool = false

    var icon: String {
        if isDirectory { return "folder.fill" }
        let ext = path.pathExtension.lowercased()
        switch ext {
        case "md", "markdown": return "doc.richtext"
        case "pdf": return "doc.fill"
        case "csv", "xlsx": return "tablecells"
        case "swift", "py", "js", "ts": return "chevron.left.forwardslash.chevron.right"
        case "json", "yaml", "yml": return "curlybraces"
        case "png", "jpg", "jpeg", "gif": return "photo"
        case "txt": return "doc.text"
        default: return "doc"
        }
    }

    var iconColor: Color {
        if isDirectory { return MacColors.amberAccent }
        let ext = path.pathExtension.lowercased()
        switch ext {
        case "md", "markdown": return Color(hex: "026DFF")
        case "pdf": return Color(hex: "FF3B30")
        case "swift": return Color(hex: "F05138")
        case "py": return Color(hex: "3776AB")
        case "json", "yaml", "yml": return MacColors.healthGreen
        default: return MacColors.textSecondary
        }
    }
}

/// Manages file tree state, traversal, and search for the Explorer view.
@MainActor
class MacExplorerViewModel: ObservableObject {
    @Published var rootNodes: [FileNode] = []
    @Published var selectedFile: FileNode?
    @Published var searchText: String = ""
    @Published var selectedFormat: FileFormat = .all
    @Published var isLoadingPreview: Bool = false
    @Published var previewContent: String = ""
    @Published var hasRootFolder: Bool = false

    enum FileFormat: String, CaseIterable {
        case all = "All"
        case markdown = "Markdown"
        case pdf = "PDF"
        case csv = "CSV"
    }

    // MARK: - Folder Selection

    func selectRootFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.message = "Select a folder to explore"

        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else { return }
            Task { @MainActor in
                self?.loadDirectory(at: url)
            }
        }
    }

    func loadDirectory(at url: URL) {
        hasRootFolder = true
        rootNodes = buildTree(at: url, depth: 0, maxDepth: 3)
    }

    // MARK: - Tree Building

    private func buildTree(at url: URL, depth: Int, maxDepth: Int) -> [FileNode] {
        guard depth < maxDepth else { return [] }

        let fileManager = FileManager.default
        guard let contents = try? fileManager.contentsOfDirectory(
            at: url,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else {
            return []
        }

        return contents
            .sorted { $0.lastPathComponent.localizedCompare($1.lastPathComponent) == .orderedAscending }
            .compactMap { itemURL in
                let isDir = (try? itemURL.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
                let children = isDir ? buildTree(at: itemURL, depth: depth + 1, maxDepth: maxDepth) : nil
                return FileNode(
                    name: itemURL.lastPathComponent,
                    path: itemURL,
                    isDirectory: isDir,
                    children: children
                )
            }
    }

    // MARK: - File Selection & Preview

    func selectFile(_ node: FileNode) {
        guard !node.isDirectory else { return }
        selectedFile = node
        loadPreview(for: node)
    }

    private func loadPreview(for node: FileNode) {
        isLoadingPreview = true
        previewContent = ""

        let url = node.path
        let ext = url.pathExtension.lowercased()

        switch ext {
        case "md", "markdown", "txt", "swift", "py", "js", "ts", "json", "yaml", "yml", "csv":
            if let content = try? String(contentsOf: url, encoding: .utf8) {
                // Limit to first 5000 chars for performance
                previewContent = String(content.prefix(5000))
            } else {
                previewContent = "Unable to read file."
            }
        case "pdf":
            previewContent = "[PDF Preview — use Quick Look for full rendering]"
        default:
            previewContent = "Preview not available for .\(ext) files."
        }

        isLoadingPreview = false
    }

    // MARK: - Toggle Expansion

    func toggleExpansion(_ nodeId: UUID) {
        toggleExpansionIn(&rootNodes, id: nodeId)
    }

    private func toggleExpansionIn(_ nodes: inout [FileNode], id: UUID) {
        for index in nodes.indices {
            if nodes[index].id == id {
                nodes[index].isExpanded.toggle()
                return
            }
            if nodes[index].children != nil {
                // Force unwrap is safe: nil-checked on line above.
                // Required for inout access to Optional's wrapped value.
                toggleExpansionIn(&nodes[index].children!, id: id)
            }
        }
    }

    // MARK: - Filtered Nodes

    var filteredNodes: [FileNode] {
        guard !searchText.isEmpty || selectedFormat != .all else { return rootNodes }
        return filterNodes(rootNodes)
    }

    private func filterNodes(_ nodes: [FileNode]) -> [FileNode] {
        nodes.compactMap { node in
            if node.isDirectory {
                let filteredChildren = filterNodes(node.children ?? [])
                if filteredChildren.isEmpty { return nil }
                var filtered = node
                filtered.children = filteredChildren
                return filtered
            }

            let matchesSearch = searchText.isEmpty || node.name.localizedCaseInsensitiveContains(searchText)
            let matchesFormat: Bool = {
                switch selectedFormat {
                case .all: return true
                case .markdown: return ["md", "markdown"].contains(node.path.pathExtension.lowercased())
                case .pdf: return node.path.pathExtension.lowercased() == "pdf"
                case .csv: return node.path.pathExtension.lowercased() == "csv"
                }
            }()

            return (matchesSearch && matchesFormat) ? node : nil
        }
    }
}
