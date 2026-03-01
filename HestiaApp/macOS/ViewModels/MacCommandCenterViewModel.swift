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
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // Derived stat counts
    var healthStatus: String { systemHealth?.status.displayText ?? "Unknown" }
    var pendingMemoryCount: Int { pendingMemories.count }
    var activeOrderCount: Int { orders.filter { $0.status == .active }.count }
    var todayEventCount: Int { calendarEvents.count }

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

        _ = await (healthTask, memoryTask, ordersTask, calendarTask, newsfeedTask)
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
