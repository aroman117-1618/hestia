import Foundation
import SwiftUI
import HestiaShared

@MainActor
class MacExplorerResourcesViewModel: ObservableObject {
    @Published var resources: [ExplorerResource] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var searchText = ""
    @Published var selectedType: ExplorerResourceType?

    private let client = APIClient.shared

    static let filterTabs: [(label: String, type: ExplorerResourceType?)] = [
        ("All", nil),
        ("Drafts", .draft),
        ("Inbox", .mail),
        ("Tasks", .task),
        ("Notes", .note),
        ("Files", .file),
    ]

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
            print("[ExplorerResources] Load failed: \(error)")
            #endif
            errorMessage = "Failed to load resources"
        }

        isLoading = false
    }

    func applyFilter(type: ExplorerResourceType?) async {
        selectedType = type
        await loadResources()
    }

    func search() async {
        await loadResources()
    }

    func createDraft(title: String, body: String? = nil) async {
        do {
            let draft = try await client.createDraft(title: title, body: body)
            resources.insert(draft, at: 0)
        } catch {
            #if DEBUG
            print("[ExplorerResources] Create draft failed: \(error)")
            #endif
            errorMessage = "Failed to create draft"
        }
    }

    func deleteDraft(_ resource: ExplorerResource) async {
        do {
            _ = try await client.deleteDraft(id: resource.id)
            resources.removeAll { $0.id == resource.id }
        } catch {
            #if DEBUG
            print("[ExplorerResources] Delete draft failed: \(error)")
            #endif
            errorMessage = "Failed to delete draft"
        }
    }
}
