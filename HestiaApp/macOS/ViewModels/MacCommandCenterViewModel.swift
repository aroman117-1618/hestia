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
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // Learning metrics
    @Published var metaMonitorReport: MetaMonitorReport?
    @Published var memoryHealth: MemoryHealthSnapshot?
    @Published var triggerAlerts: [TriggerAlert] = []

    // Derived stat counts
    var healthStatus: String { systemHealth?.status.displayText ?? "Unknown" }
    var pendingMemoryCount: Int { pendingMemories.count }
    var activeOrderCount: Int { orders.filter { $0.status == .active }.count }
    var todayEventCount: Int { calendarEvents.count }

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

    // MARK: - Data Loading

    func loadAllData() async {
        isLoading = true
        errorMessage = nil

        async let healthTask: () = loadHealth()
        async let memoryTask: () = loadPendingMemories()
        async let ordersTask: () = loadOrders()
        async let calendarTask: () = loadCalendarEvents()
        async let newsfeedTask: () = loadNewsfeed()
        async let learningTask: () = loadLearningMetrics()
        async let investigateTask: () = loadInvestigations()
        async let healthSummaryTask: () = loadHealthSummary()

        _ = await (healthTask, memoryTask, ordersTask, calendarTask, newsfeedTask, learningTask, investigateTask, healthSummaryTask)
        isLoading = false
    }

    private func loadHealth() async {
        do {
            systemHealth = try await APIClient.shared.getSystemHealth()
        } catch {
            #if DEBUG
            print("[MacCommandCenterVM] Health load failed: \(error)")
            #endif
        }
    }

    private func loadPendingMemories() async {
        do {
            pendingMemories = try await APIClient.shared.getPendingMemoryReviews()
        } catch {
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
            #if DEBUG
            print("[MacCommandCenterVM] MetaMonitor load failed: \(error)")
            #endif
        }

        do {
            let healthResponse = try await APIClient.shared.getMemoryHealth()
            memoryHealth = healthResponse.data
        } catch {
            #if DEBUG
            print("[MacCommandCenterVM] Memory health load failed: \(error)")
            #endif
        }

        do {
            let alertsResponse = try await APIClient.shared.getTriggerAlerts()
            triggerAlerts = alertsResponse.data
        } catch {
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
            #if DEBUG
            print("[MacCommandCenterVM] Investigations load failed: \(error)")
            #endif
        }
    }

    private func loadHealthSummary() async {
        do {
            healthSummary = try await APIClient.shared.getHealthSummary()
        } catch {
            #if DEBUG
            print("[MacCommandCenterVM] Health summary load failed: \(error)")
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
