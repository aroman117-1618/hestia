#if os(iOS)
import SwiftUI
import HestiaShared

/// Manages Explorer state: resource loading, filtering, search
@MainActor
class ExplorerViewModel: ObservableObject {
    @Published var resources: [ExplorerResource] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var searchText = ""
    @Published var selectedType: ExplorerResourceType?
    @Published var selectedResource: ExplorerResource?

    private let client = APIClient.shared

    /// Section tabs for filtering
    static let filterTabs: [(label: String, type: ExplorerResourceType?)] = [
        ("All", nil),
        ("Drafts", .draft),
        ("Inbox", .mail),
        ("Tasks", .task),
        ("Notes", .note),
        ("Files", .file),
    ]

    /// Load resources from backend
    func loadResources() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await client.getExplorerResources(
                type: selectedType,
                search: searchText.isEmpty ? nil : searchText
            )
            resources = response.resources
        } catch {
            #if DEBUG
            print("[Explorer] Load failed: \(error)")
            #endif
            errorMessage = "Failed to load resources"
        }

        isLoading = false
    }

    /// Refresh when filter or search changes
    func applyFilter(type: ExplorerResourceType?) async {
        selectedType = type
        await loadResources()
    }

    /// Search with debounce handled by caller
    func search() async {
        await loadResources()
    }

    /// Create a new draft
    func createDraft(title: String, body: String? = nil) async {
        do {
            let draft = try await client.createDraft(title: title, body: body)
            resources.insert(draft, at: 0)
        } catch {
            #if DEBUG
            print("[Explorer] Create draft failed: \(error)")
            #endif
            errorMessage = "Failed to create draft"
        }
    }

    /// Delete a draft
    func deleteDraft(_ resource: ExplorerResource) async {
        do {
            _ = try await client.deleteDraft(id: resource.id)
            resources.removeAll { $0.id == resource.id }
        } catch {
            #if DEBUG
            print("[Explorer] Delete draft failed: \(error)")
            #endif
            errorMessage = "Failed to delete draft"
        }
    }
}
#endif
