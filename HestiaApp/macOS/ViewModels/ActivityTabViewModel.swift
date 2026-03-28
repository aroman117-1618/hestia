import SwiftUI
import HestiaShared

/// ViewModel for the Activity tab — unified feed of completed orders,
/// alerts, system events, and self-dev suggestions.
@MainActor
class ActivityTabViewModel: ObservableObject {

    // MARK: - Feed Filter

    enum FeedFilter: String, CaseIterable, Identifiable {
        case all = "All"
        case orders = "Orders"
        case alerts = "Alerts"
        case system = "System"
        var id: String { rawValue }
    }

    // MARK: - Published State

    @Published var feedItems: [NewsfeedItem] = []
    @Published var activeFilter: FeedFilter = .all
    @Published var selectedItemId: String?
    @Published var isPanelOpen = false
    @Published var isLoading = false

    // Detail panel data
    @Published var selectedRunDetail: WorkflowRunDetail?
    @Published var isLoadingDetail = false

    // MARK: - Computed

    var filteredItems: [NewsfeedItem] {
        guard activeFilter != .all else { return feedItems }
        return feedItems.filter { item in
            switch activeFilter {
            case .all: return true
            case .orders: return item.source == "orders" || item.itemType == "order_execution"
            case .alerts: return item.source == "trading" || item.source == "sentinel" || item.priority == "high"
            case .system: return item.source == "system" || item.source == "newsfeed"
            }
        }
    }

    var selectedItem: NewsfeedItem? {
        feedItems.first { $0.id == selectedItemId }
    }

    // MARK: - Public API

    func loadData() async {
        isLoading = feedItems.isEmpty
        defer { isLoading = false }

        let (data, _) = await CacheFetcher.load(
            key: CacheKey.newsfeed,
            ttl: CacheTTL.frequent
        ) {
            try await APIClient.shared.getNewsfeedTimeline(limit: 50)
        }
        if let data {
            feedItems = data.items
        }
    }

    func selectItem(_ item: NewsfeedItem) {
        selectedItemId = item.id
        withAnimation(.easeInOut(duration: 0.25)) {
            isPanelOpen = true
        }
        // If order execution, load run detail
        if item.itemType == "order_execution", let actionId = item.actionId {
            Task { await loadRunDetail(actionId) }
        }
    }

    func closePanel() {
        withAnimation(.easeInOut(duration: 0.25)) {
            isPanelOpen = false
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
            self?.selectedItemId = nil
            self?.selectedRunDetail = nil
        }
    }

    func sendToChat(_ context: String) {
        NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            NotificationCenter.default.post(
                name: .hestiaSendToChat,
                object: nil,
                userInfo: ["context": context]
            )
        }
    }

    // MARK: - Private

    private func loadRunDetail(_ runId: String) async {
        isLoadingDetail = true
        defer { isLoadingDetail = false }
        do {
            let parts = runId.split(separator: ":")
            if parts.count == 2 {
                let workflowId = String(parts[0])
                let actualRunId = String(parts[1])
                selectedRunDetail = try await APIClient.shared.getRunDetail(workflowId, runId: actualRunId)
            }
        } catch {
            #if DEBUG
            print("[ActivityTab] Run detail load failed: \(error)")
            #endif
        }
    }
}
