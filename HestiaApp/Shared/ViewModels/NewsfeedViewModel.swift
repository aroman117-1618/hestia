import SwiftUI
import HestiaShared
import Combine

/// ViewModel for the unified newsfeed timeline
@MainActor
class NewsfeedViewModel: ObservableObject {
    // MARK: - Published State

    @Published var items: [NewsfeedItem] = []
    @Published var unreadCount: Int = 0
    @Published var unreadByType: [String: Int] = [:]
    @Published var selectedFilter: NewsfeedItemType? = nil
    @Published var briefing: BriefingResponse? = nil
    @Published var isLoading = false
    @Published var isBriefingLoading = false
    @Published var isBriefingExpanded = true
    @Published var error: String? = nil

    // MARK: - Computed

    var filteredItems: [NewsfeedItem] {
        guard let filter = selectedFilter else { return items }
        return items.filter { $0.type == filter }
    }

    var hasItems: Bool {
        !filteredItems.isEmpty
    }

    // MARK: - Load Timeline

    func loadTimeline() async {
        isLoading = true
        error = nil

        do {
            let response = try await APIClient.shared.getNewsfeedTimeline(
                type: selectedFilter
            )
            items = response.items
            unreadCount = response.unreadCount
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to load timeline: \(error)")
            #endif
            self.error = "Failed to load timeline"
        }

        isLoading = false
    }

    // MARK: - Load Unread Counts

    func loadUnreadCounts() async {
        do {
            let response = try await APIClient.shared.getNewsfeedUnreadCount()
            unreadCount = response.total
            unreadByType = response.byType
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to load unread counts: \(error)")
            #endif
        }
    }

    // MARK: - Load Briefing

    func loadBriefing() async {
        isBriefingLoading = true

        do {
            briefing = try await APIClient.shared.getBriefing()
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to load briefing: \(error)")
            #endif
        }

        isBriefingLoading = false
    }

    // MARK: - Actions

    func markRead(_ itemId: String) async {
        do {
            _ = try await APIClient.shared.markNewsfeedItemRead(itemId: itemId)
            await loadTimeline()
            await loadUnreadCounts()
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to mark read: \(error)")
            #endif
        }
    }

    func dismiss(_ itemId: String) async {
        // Optimistic UI: remove immediately
        items.removeAll { $0.id == itemId }

        do {
            _ = try await APIClient.shared.dismissNewsfeedItem(itemId: itemId)
            await loadUnreadCounts()
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to dismiss: \(error)")
            #endif
            await loadTimeline()
        }
    }

    func refresh() async {
        do {
            _ = try await APIClient.shared.refreshNewsfeed()
        } catch {
            #if DEBUG
            print("[NewsfeedViewModel] Failed to refresh: \(error)")
            #endif
        }
        await loadTimeline()
        await loadUnreadCounts()
    }

    func setFilter(_ type: NewsfeedItemType?) {
        selectedFilter = type
        Task {
            await loadTimeline()
        }
    }
}
