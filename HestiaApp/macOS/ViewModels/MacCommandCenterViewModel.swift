import SwiftUI
import HestiaShared
import EventKit

/// Aggregates data for the Command Center dashboard.
@MainActor
class MacCommandCenterViewModel: ObservableObject {
    // MARK: - Published State

    @Published var systemHealth: SystemHealth?
    @Published var pendingMemories: [MemoryChunk] = []
    @Published var orders: [OrderResponse] = []
    @Published var calendarEvents: [EKEvent] = []
    @Published var newsfeedItems: [NewsfeedItem] = []
    @Published var unreadCount: Int = 0
    @Published var investigations: [Investigation] = []
    @Published var healthSummary: MacHealthSummaryResponse?
    @Published var tradingSummary: TradingSummary?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var lastUpdated: Date?

    // Track which sections failed for graceful degradation
    @Published var failedSections: Set<String> = []

    // Learning metrics
    @Published var metaMonitorReport: MetaMonitorReport?
    @Published var memoryHealth: MemoryHealthSnapshot?
    @Published var triggerAlerts: [TriggerAlert] = []

    // Derived stat counts
    var healthStatus: String { systemHealth?.status.displayText ?? "Unknown" }
    var pendingMemoryCount: Int { pendingMemories.count }
    var activeOrderCount: Int { orders.filter { $0.status == .active }.count }
    var todayEventCount: Int { calendarEvents.count }
    var serverIsReachable: Bool { systemHealth != nil }

    // Learning derived
    var positiveRatioPercent: Int {
        guard let ratio = metaMonitorReport?.positiveRatio else { return 0 }
        return Int(ratio * 100)
    }
    var unacknowledgedAlertCount: Int { triggerAlerts.filter { !$0.acknowledged }.count }
    var memoryChunkCount: Int { memoryHealth?.chunkCount ?? 0 }
    var memoryRedundancyPct: Double { memoryHealth?.redundancyEstimatePct ?? 0.0 }

    // MARK: - Private

    private let eventStore = EKEventStore()
    private weak var errorState: ErrorState?

    // MARK: - Configuration

    /// Call from the View's onAppear to provide ErrorState reference.
    func configure(errorState: ErrorState) {
        self.errorState = errorState
    }

    // MARK: - Data Loading

    func loadAllData() async {
        let hasCachedData = CacheManager.shared.has(forKey: CacheKey.systemHealth)
        if !hasCachedData { isLoading = true }
        errorMessage = nil
        failedSections = []

        async let healthTask: () = loadHealth()
        async let memoryTask: () = loadPendingMemories()
        async let ordersTask: () = loadOrders()
        async let calendarTask: () = loadCalendarEvents()
        async let newsfeedTask: () = loadNewsfeed()
        async let learningTask: () = loadLearningMetrics()
        async let investigateTask: () = loadInvestigations()
        async let healthSummaryTask: () = loadHealthSummary()
        async let tradingTask: () = loadTradingSummary()

        _ = await (healthTask, memoryTask, ordersTask, calendarTask, newsfeedTask, learningTask, investigateTask, healthSummaryTask, tradingTask)

        // If health check failed AND no cached health data, server is likely down
        if failedSections.contains("health") && systemHealth == nil {
            let msg = "Can't reach Hestia server"
            errorMessage = msg
            errorState?.show(msg, severity: .error, duration: 10.0)
        } else if failedSections.contains("health") {
            // Server down but we have cached data — show softer warning
            errorState?.show("Server unreachable — showing cached data", severity: .warning, duration: 6.0)
        }

        lastUpdated = Date()
        isLoading = false
    }

    private func loadHealth() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.systemHealth, ttl: CacheTTL.frequent) {
            try await APIClient.shared.getSystemHealth()
        }
        systemHealth = data
        if source == .empty { failedSections.insert("health") }
    }

    private func loadPendingMemories() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.pendingMemories, ttl: CacheTTL.standard) {
            try await APIClient.shared.getPendingMemoryReviews()
        }
        pendingMemories = data ?? []
        if source == .empty { failedSections.insert("memory") }
    }

    private func loadOrders() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.orders, ttl: CacheTTL.frequent) {
            try await APIClient.shared.listOrders(limit: 20)
        }
        orders = data?.orders ?? []
        if source == .empty { failedSections.insert("orders") }
    }

    private func loadCalendarEvents() async {
        let status = EKEventStore.authorizationStatus(for: .event)
        guard status == .fullAccess || status == .authorized else {
            requestCalendarAccess()
            return
        }

        let calendar = Calendar.current
        let startOfWeek = calendar.date(from: calendar.dateComponents([.yearForWeekOfYear, .weekOfYear], from: Date())) ?? Date()
        let endOfWeek = calendar.date(byAdding: .day, value: 7, to: startOfWeek) ?? Date()

        let predicate = eventStore.predicateForEvents(withStart: startOfWeek, end: endOfWeek, calendars: nil)
        let events = eventStore.events(matching: predicate)
            .filter { !$0.isAllDay }
            .sorted { $0.startDate < $1.startDate }

        calendarEvents = events
    }

    private func loadNewsfeed() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.newsfeed, ttl: CacheTTL.standard) {
            try await APIClient.shared.getNewsfeedTimeline(limit: 20)
        }
        if let data {
            newsfeedItems = data.items
            unreadCount = data.unreadCount
        }
        if source == .empty { failedSections.insert("newsfeed") }
    }

    private func loadLearningMetrics() async {
        let (report, s1) = await CacheFetcher.load(key: CacheKey.metaMonitorReport, ttl: CacheTTL.standard) {
            try await APIClient.shared.getLatestMetaMonitorReport()
        }
        metaMonitorReport = report?.data
        if s1 == .empty { failedSections.insert("metaMonitor") }

        let (health, s2) = await CacheFetcher.load(key: CacheKey.memoryHealth, ttl: CacheTTL.standard) {
            try await APIClient.shared.getMemoryHealth()
        }
        memoryHealth = health?.data
        if s2 == .empty { failedSections.insert("memoryHealth") }

        let (alerts, s3) = await CacheFetcher.load(key: CacheKey.triggerAlerts, ttl: CacheTTL.standard) {
            try await APIClient.shared.getTriggerAlerts()
        }
        triggerAlerts = alerts?.data ?? []
        if s3 == .empty { failedSections.insert("alerts") }
    }

    private func loadInvestigations() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.investigations, ttl: CacheTTL.standard) {
            try await APIClient.shared.getInvestigationHistory(limit: 20)
        }
        investigations = data?.investigations ?? []
        if source == .empty { failedSections.insert("investigations") }
    }

    private func loadHealthSummary() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.healthSummary, ttl: CacheTTL.standard) {
            try await APIClient.shared.getHealthSummary()
        }
        healthSummary = data
        if source == .empty { failedSections.insert("healthSummary") }
    }

    private func loadTradingSummary() async {
        let (data, source) = await CacheFetcher.load(key: CacheKey.tradingSummary, ttl: CacheTTL.realtime) {
            try await APIClient.shared.getTradingSummary()
        }
        tradingSummary = data
        if source == .empty { failedSections.insert("trading") }
    }

    private func requestCalendarAccess() {
        if #available(macOS 14.0, *) {
            eventStore.requestFullAccessToEvents { [weak self] granted, _ in
                if granted {
                    Task { @MainActor in
                        await self?.loadCalendarEvents()
                    }
                }
            }
        } else {
            eventStore.requestAccess(to: .event) { [weak self] granted, _ in
                if granted {
                    Task { @MainActor in
                        await self?.loadCalendarEvents()
                    }
                }
            }
        }
    }
}
