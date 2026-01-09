import SwiftUI
import Combine
import CoreData

/// ViewModel for the Command Center (modular widgets dashboard)
@MainActor
class CommandCenterViewModel: ObservableObject {
    // MARK: - Published State

    // Calendar
    @Published var nextEvent: CalendarEvent?
    @Published var isCalendarLoading = false
    @Published var isCalendarAuthorized = false

    // Orders
    @Published var orders: [Order] = []
    @Published var recentExecutions: [OrderExecution] = []
    @Published var isOrdersLoading = false

    // Memory
    @Published var pendingMemoryCount: Int = 0

    // UI State
    @Published var isOrderFormExpanded = false
    @Published var selectedTab: CommandTab = .orders
    @Published var alertCount: Int = 0
    @Published var isLoading: Bool = false

    // MARK: - Tab Options

    enum CommandTab: String, CaseIterable {
        case orders = "Orders"
        case alerts = "Alerts"
        case memory = "Memory"
    }

    // MARK: - Dependencies

    private let calendarService: CalendarService
    private let ordersService: OrdersService
    private let client: HestiaClientProtocol
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    init(
        calendarService: CalendarService = CalendarService(),
        ordersService: OrdersService = OrdersService(),
        client: HestiaClientProtocol = MockHestiaClient()
    ) {
        self.calendarService = calendarService
        self.ordersService = ordersService
        self.client = client

        // Initialize calendar service on main actor
        calendarService.setup()

        // Observe calendar service state
        calendarService.$nextEvent
            .receive(on: DispatchQueue.main)
            .assign(to: &$nextEvent)

        calendarService.$isAuthorized
            .receive(on: DispatchQueue.main)
            .assign(to: &$isCalendarAuthorized)

        calendarService.$isLoading
            .receive(on: DispatchQueue.main)
            .assign(to: &$isCalendarLoading)

        // Observe orders service state
        ordersService.$orders
            .receive(on: DispatchQueue.main)
            .assign(to: &$orders)

        ordersService.$recentExecutions
            .receive(on: DispatchQueue.main)
            .assign(to: &$recentExecutions)

        ordersService.$isLoading
            .receive(on: DispatchQueue.main)
            .assign(to: &$isOrdersLoading)

        // Calculate alert count from executions
        $recentExecutions
            .map { executions in
                executions.filter { $0.status == .failed }.count
            }
            .assign(to: &$alertCount)
    }

    // MARK: - Public Methods

    /// Refresh all data
    func refresh() async {
        isLoading = true

        // Request calendar access if not authorized
        if !isCalendarAuthorized {
            _ = await calendarService.requestAccess()
        }

        // Fetch calendar event
        _ = await calendarService.fetchNextEvent()

        // Start auto-refresh for countdown
        calendarService.startAutoRefresh(interval: 60)

        // Fetch orders
        _ = try? await ordersService.fetchOrders()

        // Fetch recent executions
        _ = try? await ordersService.fetchRecentExecutions()

        // Fetch pending memory reviews count
        do {
            let pendingReviews = try await client.getPendingMemoryReviews()
            pendingMemoryCount = pendingReviews.count
        } catch {
            #if DEBUG
            print("[CommandCenterViewModel] Failed to fetch pending memory reviews: \(error)")
            #endif
        }

        isLoading = false
    }

    /// Stop refresh timers (call when view disappears)
    func stopRefresh() {
        calendarService.stopAutoRefresh()
    }

    // MARK: - Order Actions

    func addOrder(_ order: Order) {
        Task {
            do {
                _ = try await ordersService.createOrder(order)
            } catch {
                #if DEBUG
                print("[CommandCenterViewModel] Failed to create order: \(error)")
                #endif
            }
        }
    }

    func toggleOrderStatus(_ orderId: UUID) {
        Task {
            do {
                _ = try await ordersService.toggleOrderStatus(orderId)
            } catch {
                #if DEBUG
                print("[CommandCenterViewModel] Failed to toggle order: \(error)")
                #endif
            }
        }
    }

    func deleteOrder(_ orderId: UUID) {
        Task {
            do {
                try await ordersService.deleteOrder(orderId)
            } catch {
                #if DEBUG
                print("[CommandCenterViewModel] Failed to delete order: \(error)")
                #endif
            }
        }
    }

    func retryOrder(_ orderId: UUID) {
        Task {
            do {
                try await ordersService.retryOrder(orderId)
            } catch {
                #if DEBUG
                print("[CommandCenterViewModel] Failed to retry order: \(error)")
                #endif
            }
        }
    }
}

// MARK: - Legacy Supporting Models (for backward compatibility)

struct Meeting: Identifiable {
    let id: String
    let title: String
    let location: String?
    let startsAt: Date
    let startsInMinutes: Int
}

struct Automation: Identifiable {
    let id: String
    let name: String
    let icon: String
    let alertCount: Int
    let isEnabled: Bool
}

struct Activity: Identifiable {
    let id: String
    let title: String
    let subtitle: String
    let icon: String
    let color: String // Hex color
    let timestamp: Date

    var formattedTime: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: timestamp)
    }
}
