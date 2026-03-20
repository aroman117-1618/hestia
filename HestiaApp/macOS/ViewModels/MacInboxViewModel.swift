import SwiftUI
import HestiaShared

// MARK: - Inbox ViewModel (API-backed)

@MainActor
class MacInboxViewModel: ObservableObject {
    // MARK: - Published State

    @Published var items: [InboxItemResponse] = []
    @Published var selectedItem: InboxItemResponse? = nil
    @Published var isLoading = false
    @Published var isLoadingDetail = false
    @Published var error: String? = nil
    @Published var selectedSource: String? = nil  // nil = all
    @Published var unreadCount: Int = 0
    @Published var unreadBySource: [String: Int] = [:]

    // MARK: - Computed Properties

    var hasError: Bool { error != nil }

    var filteredItems: [InboxItemResponse] {
        guard let source = selectedSource else { return items }
        return items.filter { $0.source == source }
    }

    // MARK: - Load Inbox

    func loadInbox() async {
        if !CacheManager.shared.has(forKey: CacheKey.inboxItems) {
            isLoading = true
        }
        error = nil

        let (response, source) = await CacheFetcher.load(
            key: CacheKey.inboxItems,
            ttl: CacheTTL.standard
        ) { [selectedSource] in
            try await APIClient.shared.getInbox(
                source: selectedSource,
                limit: 100,
                offset: 0
            )
        }

        if let response {
            items = response.items
            #if DEBUG
            print("[Inbox] Loaded \(response.items.count) items (total: \(response.total))")
            #endif
        } else if source == .empty {
            self.error = "Failed to load inbox"
        }

        isLoading = false

        // Also fetch unread counts
        await loadUnreadCounts()
    }

    // MARK: - Unread Counts

    func loadUnreadCounts() async {
        do {
            let response = try await APIClient.shared.getInboxUnreadCount()
            unreadCount = response.total
            unreadBySource = response.bySource
            #if DEBUG
            print("[Inbox] Unread: \(response.total) total, by source: \(response.bySource)")
            #endif
        } catch {
            #if DEBUG
            print("[Inbox] Error loading unread counts: \(error)")
            #endif
        }
    }

    // MARK: - Select Item (marks read + loads detail)

    func selectItem(_ item: InboxItemResponse) async {
        selectedItem = item

        // Mark as read if unread
        if !item.isRead {
            isLoadingDetail = true
            do {
                let updated = try await APIClient.shared.markInboxItemRead(id: item.id)
                // Update in list
                if let index = items.firstIndex(where: { $0.id == item.id }) {
                    items[index] = updated
                }
                selectedItem = updated
                isLoadingDetail = false

                // Refresh unread counts
                await loadUnreadCounts()
            } catch {
                isLoadingDetail = false
                #if DEBUG
                print("[Inbox] Error marking read: \(error)")
                #endif
            }
        }
    }

    // MARK: - Mark All Read

    func markAllRead() async {
        do {
            let response = try await APIClient.shared.markAllInboxRead(source: selectedSource)
            #if DEBUG
            print("[Inbox] Marked \(response.markedCount) items as read")
            #endif

            // Reload to get updated states
            await loadInbox()
        } catch {
            self.error = "Failed to mark all as read"
            #if DEBUG
            print("[Inbox] Error marking all read: \(error)")
            #endif
        }
    }

    // MARK: - Archive Item

    func archiveItem(_ item: InboxItemResponse) async {
        do {
            _ = try await APIClient.shared.archiveInboxItem(id: item.id)

            // Remove from list
            items.removeAll { $0.id == item.id }
            if selectedItem?.id == item.id {
                selectedItem = nil
            }

            // Refresh unread counts
            await loadUnreadCounts()

            #if DEBUG
            print("[Inbox] Archived \(item.title)")
            #endif
        } catch {
            self.error = "Failed to archive item"
            #if DEBUG
            print("[Inbox] Error archiving: \(error)")
            #endif
        }
    }

    // MARK: - Refresh

    func refresh() async {
        do {
            let response = try await APIClient.shared.refreshInbox()
            #if DEBUG
            print("[Inbox] Refreshed \(response.refreshed) items from sources")
            #endif

            // Reload after refresh
            await loadInbox()
        } catch {
            self.error = "Failed to refresh inbox"
            #if DEBUG
            print("[Inbox] Error refreshing: \(error)")
            #endif
        }
    }

    // MARK: - Filter by Source

    func filterBySource(_ source: String?) async {
        selectedSource = source
        selectedItem = nil
        await loadInbox()
    }
}
