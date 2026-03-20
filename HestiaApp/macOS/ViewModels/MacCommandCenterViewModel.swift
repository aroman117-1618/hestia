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
        isLoading = true
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

        // If health check failed, server is likely down — show banner
        if failedSections.contains("health") {
            let msg = "Can't reach Hestia server"
            errorMessage = msg
            errorState?.show(msg, severity: .error, duration: 10.0)
        }

        lastUpdated = Date()
        isLoading = false
    }

    private func loadHealth() async {
        do {
            systemHealth = try await APIClient.shared.getSystemHealth()
        } catch {
            failedSections.insert("health")
            #if DEBUG
            print("[MacCommandCenterVM] Health load failed: \(error)")
            #endif
        }
    }

    private func loadPendingMemories() async {
        do {
            pendingMemories = try await APIClient.shared.getPendingMemoryReviews()
        } catch {
            failedSections.insert("memory")
            #if DEBUG
            print("[MacCommandCenterVM] Memory load failed: \(error)")
            #endif
        }
    }

    private func loadOrders() async {
        do {
            let response = try await APIClient.shared.listOrders(limit: 20)
            orders = response.orders
        } catch {
            failedSections.insert("orders")
            #if DEBUG
            print("[MacCommandCenterVM] Orders load failed: \(error)")
            #endif
        }
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
        do {
            let response = try await APIClient.shared.getNewsfeedTimeline(limit: 20)
            newsfeedItems = response.items
            unreadCount = response.unreadCount
        } catch {
            failedSections.insert("newsfeed")
            #if DEBUG
            print("[MacCommandCenterVM] Newsfeed load failed: \(error)")
            #endif
        }
    }

    private func loadLearningMetrics() async {
        do {
            let reportResponse = try await APIClient.shared.getLatestMetaMonitorReport()
            metaMonitorReport = reportResponse.data
        } catch {
            failedSections.insert("metaMonitor")
            #if DEBUG
            print("[MacCommandCenterVM] MetaMonitor load failed: \(error)")
            #endif
        }

        do {
            let healthResponse = try await APIClient.shared.getMemoryHealth()
            memoryHealth = healthResponse.data
        } catch {
            failedSections.insert("memoryHealth")
            #if DEBUG
            print("[MacCommandCenterVM] Memory health load failed: \(error)")
            #endif
        }

        do {
            let alertsResponse = try await APIClient.shared.getTriggerAlerts()
            triggerAlerts = alertsResponse.data
        } catch {
            failedSections.insert("alerts")
            #if DEBUG
            print("[MacCommandCenterVM] Alerts load failed: \(error)")
            #endif
        }
    }

    private func loadInvestigations() async {
        do {
            let response = try await APIClient.shared.getInvestigationHistory(limit: 20)
            investigations = response.investigations
        } catch {
            failedSections.insert("investigations")
            #if DEBUG
            print("[MacCommandCenterVM] Investigations load failed: \(error)")
            #endif
        }
    }

    private func loadHealthSummary() async {
        do {
            healthSummary = try await APIClient.shared.getHealthSummary()
        } catch {
            failedSections.insert("healthSummary")
            #if DEBUG
            print("[MacCommandCenterVM] Health summary load failed: \(error)")
            #endif
        }
    }

    private func loadTradingSummary() async {
        do {
            tradingSummary = try await APIClient.shared.getTradingSummary()
        } catch {
            failedSections.insert("trading")
            #if DEBUG
            print("[MacCommandCenterVM] Trading summary load failed: \(error)")
            #endif
        }
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
