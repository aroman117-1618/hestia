import SwiftUI
import HestiaShared

/// ViewModel for the Memory Browser — paginated chunk list with sorting and filtering.
@MainActor
class MacMemoryBrowserViewModel: ObservableObject {
    // MARK: - Published State

    @Published var chunks: [MemoryChunkItem] = []
    @Published var totalCount: Int = 0
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var currentPage: Int = 0
    @Published var sortBy: SortOption = .importance
    @Published var sortOrder: String = "desc"
    @Published var chunkTypeFilter: String?
    @Published var statusFilter: String? = "active"
    @Published var pinnedChunk: MemoryChunkItem?

    let pageSize: Int = 50

    // MARK: - Sort Options

    enum SortOption: String, CaseIterable {
        case importance = "importance"
        case created = "created"
        case updated = "updated"

        var label: String {
            switch self {
            case .importance: return "Importance"
            case .created: return "Recent"
            case .updated: return "Updated"
            }
        }
    }

    // MARK: - Derived

    var totalPages: Int { max(1, (totalCount + pageSize - 1) / pageSize) }
    var hasNextPage: Bool { currentPage < totalPages - 1 }
    var hasPreviousPage: Bool { currentPage > 0 }

    // MARK: - Data Loading

    func loadChunks() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let response = try await APIClient.shared.listMemoryChunks(
                limit: pageSize,
                offset: currentPage * pageSize,
                sortBy: sortBy.rawValue,
                sortOrder: sortOrder,
                chunkType: chunkTypeFilter,
                status: statusFilter
            )
            chunks = response.chunks
            totalCount = response.total
        } catch {
            errorMessage = "Failed to load memories"
            #if DEBUG
            print("[MacMemoryBrowserVM] Load failed: \(error)")
            #endif
        }
    }

    func nextPage() async {
        guard hasNextPage else { return }
        currentPage += 1
        await loadChunks()
    }

    func previousPage() async {
        guard hasPreviousPage else { return }
        currentPage -= 1
        await loadChunks()
    }

    func resetAndLoad() async {
        currentPage = 0
        await loadChunks()
    }

    func fetchPinnedChunk(id: String) async {
        do {
            pinnedChunk = try await APIClient.shared.getChunk(id)
        } catch {
            pinnedChunk = nil
            #if DEBUG
            print("[MacMemoryBrowserVM] Failed to fetch pinned chunk: \(error)")
            #endif
        }
    }

    func updateChunk(
        id: String,
        content: String?,
        chunkType: String?,
        tags: [String]?
    ) async {
        do {
            let request = MemoryChunkUpdateRequest(content: content, chunkType: chunkType, tags: tags)
            let updated = try await APIClient.shared.updateChunk(id, request: request)
            if let idx = chunks.firstIndex(where: { $0.id == updated.id }) {
                chunks[idx] = updated
            }
        } catch {
            errorMessage = "Failed to save changes."
            #if DEBUG
            print("[MacMemoryBrowserVM] Update failed: \(error)")
            #endif
        }
    }
}
