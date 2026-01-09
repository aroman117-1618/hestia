import Foundation
import CoreData
import Combine

/// Protocol for orders service operations
protocol OrdersServiceProtocol {
    func createOrder(_ order: Order) async throws -> Order
    func updateOrder(_ order: Order) async throws -> Order
    func deleteOrder(_ orderId: UUID) async throws
    func fetchOrders() async throws -> [Order]
    func fetchRecentExecutions(limit: Int) async throws -> [OrderExecution]
    func toggleOrderStatus(_ orderId: UUID) async throws -> Order
    func retryOrder(_ orderId: UUID) async throws
    func syncOrders() async throws
}

/// Orders service with backend-first sync strategy
/// - Calls backend API first for all operations
/// - Falls back to Core Data cache when backend unavailable
/// - Updates local cache after successful backend operations
@MainActor
final class OrdersService: ObservableObject, OrdersServiceProtocol {
    // MARK: - Published State

    @Published private(set) var orders: [Order] = []
    @Published private(set) var recentExecutions: [OrderExecution] = []
    @Published private(set) var isLoading = false
    @Published private(set) var isOffline = false
    @Published private(set) var lastSyncError: Error?

    // MARK: - Private Properties

    private let viewContext: NSManagedObjectContext
    private let apiClient: APIClient

    // MARK: - Initialization

    nonisolated init(context: NSManagedObjectContext? = nil, apiClient: APIClient? = nil) {
        self.viewContext = context ?? PersistenceController.shared.viewContext
        self.apiClient = apiClient ?? APIClient.shared
    }

    // MARK: - Public Methods

    func createOrder(_ order: Order) async throws -> Order {
        isLoading = true
        defer { isLoading = false }

        // Validate order
        guard order.isValid else {
            throw OrdersError.validationFailed(order.validationErrors)
        }

        // Build API request
        let request = OrderCreateRequest(
            name: order.name,
            prompt: order.prompt,
            scheduledTime: ISO8601DateFormatter().string(from: order.scheduledTime),
            frequency: OrderFrequencyAPI(
                type: APIOrderFrequencyType(rawValue: order.frequency.typeString) ?? .once,
                minutes: order.frequency.customMinutes
            ),
            resources: order.resources.map { APIMCPResource(rawValue: $0.rawValue) ?? .calendar },
            status: order.orderStatus == .active ? APIOrderStatus.active : APIOrderStatus.inactive
        )

        do {
            // Call backend API first
            let response = try await apiClient.createOrder(request)
            isOffline = false
            lastSyncError = nil

            // Convert response to local Order model
            let createdOrder = response.toOrder()

            // Save to local cache
            try saveOrderToCache(createdOrder)

            await refreshOrders()
            return createdOrder
        } catch {
            // If backend fails, save locally only (offline mode)
            #if DEBUG
            print("[OrdersService] Backend create failed, saving locally: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            // Create local entity
            let entity = OrderEntity(context: viewContext)
            entity.id = order.id
            entity.name = order.name
            entity.prompt = order.prompt
            entity.scheduledTime = order.scheduledTime
            entity.frequencyType = order.frequency.typeString
            entity.frequencyCustomMinutes = Int16(order.frequency.customMinutes ?? 0)
            entity.resources = order.resources.map { $0.rawValue } as NSArray
            entity.orderStatus = order.orderStatus.rawValue
            entity.createdAt = order.createdAt
            entity.updatedAt = order.updatedAt
            entity.needsSync = true // Mark for sync when back online

            try viewContext.save()

            await refreshOrders()
            return order
        }
    }

    func updateOrder(_ order: Order) async throws -> Order {
        isLoading = true
        defer { isLoading = false }

        // Validate order
        guard order.isValid else {
            throw OrdersError.validationFailed(order.validationErrors)
        }

        // Build API request
        let apiRequest = OrderUpdateRequest(
            name: order.name,
            prompt: order.prompt,
            scheduledTime: ISO8601DateFormatter().string(from: order.scheduledTime),
            frequency: OrderFrequencyAPI(
                type: APIOrderFrequencyType(rawValue: order.frequency.typeString) ?? .once,
                minutes: order.frequency.customMinutes
            ),
            resources: order.resources.map { APIMCPResource(rawValue: $0.rawValue) ?? .calendar },
            status: order.orderStatus == .active ? APIOrderStatus.active : APIOrderStatus.inactive
        )

        do {
            // Call backend API first
            let response = try await apiClient.updateOrder(order.id.uuidString, request: apiRequest)
            isOffline = false
            lastSyncError = nil

            // Convert response to local Order model
            let updatedOrder = response.toOrder()

            // Update local cache
            try updateOrderInCache(updatedOrder)

            await refreshOrders()
            return updatedOrder
        } catch {
            // If backend fails, update locally only
            #if DEBUG
            print("[OrdersService] Backend update failed, updating locally: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            // Find existing entity
            let fetchRequest = OrderEntity.fetchRequest()
            fetchRequest.predicate = NSPredicate(format: "id == %@", order.id as CVarArg)

            guard let entity = try viewContext.fetch(fetchRequest).first else {
                throw OrdersError.notFound
            }

            // Update entity
            entity.update(from: order)
            entity.needsSync = true

            try viewContext.save()

            await refreshOrders()
            return order
        }
    }

    func deleteOrder(_ orderId: UUID) async throws {
        isLoading = true
        defer { isLoading = false }

        do {
            // Call backend API first
            _ = try await apiClient.deleteOrder(orderId.uuidString)
            isOffline = false
            lastSyncError = nil

            // Delete from local cache
            try deleteOrderFromCache(orderId)

            await refreshOrders()
        } catch {
            // If backend fails, mark as deleted locally
            #if DEBUG
            print("[OrdersService] Backend delete failed: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            // Still delete locally (will be synced later if needed)
            let fetchRequest = OrderEntity.fetchRequest()
            fetchRequest.predicate = NSPredicate(format: "id == %@", orderId as CVarArg)

            guard let entity = try viewContext.fetch(fetchRequest).first else {
                throw OrdersError.notFound
            }

            viewContext.delete(entity)
            try viewContext.save()

            await refreshOrders()
        }
    }

    func fetchOrders() async throws -> [Order] {
        isLoading = true
        defer { isLoading = false }

        do {
            // Try to fetch from backend first
            let response = try await apiClient.listOrders(status: nil, limit: 100, offset: 0)
            isOffline = false
            lastSyncError = nil

            // Convert and cache all orders
            let fetchedOrders = response.orders.map { $0.toOrder() }

            // Update local cache
            try syncOrdersToCache(fetchedOrders)

            orders = fetchedOrders
            return fetchedOrders
        } catch {
            // Fall back to local cache
            #if DEBUG
            print("[OrdersService] Backend fetch failed, using cache: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            let fetchRequest = OrderEntity.allOrdersRequest()
            let entities = try viewContext.fetch(fetchRequest)

            let fetchedOrders = entities.map { $0.toOrder() }
            orders = fetchedOrders

            return fetchedOrders
        }
    }

    /// Sync all orders from backend (called on app launch)
    func syncOrders() async throws {
        _ = try await fetchOrders()
    }

    func fetchRecentExecutions(limit: Int = 20) async throws -> [OrderExecution] {
        do {
            // Fetch executions for all orders from backend
            var allExecutions: [OrderExecution] = []

            // Get list of orders first
            let ordersResponse = try await apiClient.listOrders(status: nil, limit: 100, offset: 0)
            isOffline = false

            // Fetch executions for each order
            for orderResponse in ordersResponse.orders {
                let executionsResponse = try await apiClient.listOrderExecutions(orderResponse.orderId, limit: limit)
                let orderExecutions = executionsResponse.executions.map { execution -> OrderExecution in
                    OrderExecution(
                        id: UUID(uuidString: execution.executionId) ?? UUID(),
                        orderId: UUID(uuidString: orderResponse.orderId) ?? UUID(),
                        timestamp: execution.timestamp,
                        status: ExecutionStatus(rawValue: execution.status.rawValue) ?? .scheduled,
                        hestiaRead: execution.hestiaRead,
                        fullResponse: execution.fullResponse
                    )
                }
                allExecutions.append(contentsOf: orderExecutions)
            }

            // Sort by timestamp descending and limit
            allExecutions.sort { $0.timestamp > $1.timestamp }
            let limitedExecutions = Array(allExecutions.prefix(limit))

            recentExecutions = limitedExecutions
            return limitedExecutions
        } catch {
            // Fall back to local cache
            #if DEBUG
            print("[OrdersService] Backend executions fetch failed, using cache: \(error)")
            #endif
            isOffline = true

            let fetchRequest = OrderExecutionEntity.allRecentExecutionsRequest()
            fetchRequest.fetchLimit = limit

            let entities = try viewContext.fetch(fetchRequest)
            let executions = entities.map { $0.toOrderExecution() }

            recentExecutions = executions
            return executions
        }
    }

    func toggleOrderStatus(_ orderId: UUID) async throws -> Order {
        // Get current order
        let fetchRequest = OrderEntity.fetchRequest()
        fetchRequest.predicate = NSPredicate(format: "id == %@", orderId as CVarArg)

        guard let entity = try viewContext.fetch(fetchRequest).first else {
            throw OrdersError.notFound
        }

        // Toggle status
        let currentStatus = OrderStatus(rawValue: entity.orderStatus) ?? .active
        let newStatus: OrderStatus = (currentStatus == .active) ? .inactive : .active

        // Build update request with just the status change
        let apiRequest = OrderUpdateRequest(
            name: nil,
            prompt: nil,
            scheduledTime: nil,
            frequency: nil,
            resources: nil,
            status: newStatus == .active ? APIOrderStatus.active : APIOrderStatus.inactive
        )

        do {
            // Call backend API
            let response = try await apiClient.updateOrder(orderId.uuidString, request: apiRequest)
            isOffline = false
            lastSyncError = nil

            // Update local cache
            let updatedOrder = response.toOrder()
            try updateOrderInCache(updatedOrder)

            await refreshOrders()
            return updatedOrder
        } catch {
            // Fall back to local update
            #if DEBUG
            print("[OrdersService] Backend toggle failed, updating locally: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            entity.orderStatus = newStatus.rawValue
            entity.updatedAt = Date()
            entity.needsSync = true

            try viewContext.save()

            await refreshOrders()
            return entity.toOrder()
        }
    }

    func retryOrder(_ orderId: UUID) async throws {
        do {
            // Call backend to execute immediately
            let response = try await apiClient.executeOrderNow(orderId.uuidString)
            isOffline = false
            lastSyncError = nil

            #if DEBUG
            print("[OrdersService] Order executed: \(response.executionId), status: \(response.status)")
            #endif

            // Refresh to get updated data
            await refreshOrders()
            _ = try await fetchRecentExecutions()
        } catch {
            #if DEBUG
            print("[OrdersService] Backend execute failed: \(error)")
            #endif
            isOffline = true
            lastSyncError = error

            // If offline, we can't execute - just throw the error
            throw OrdersError.executionFailed("Backend unavailable: \(error.localizedDescription)")
        }
    }

    // MARK: - Private Methods

    private func refreshOrders() async {
        _ = try? await fetchOrders()
    }

    /// Save a new order to local cache
    private func saveOrderToCache(_ order: Order) throws {
        let entity = OrderEntity(context: viewContext)
        entity.id = order.id
        entity.name = order.name
        entity.prompt = order.prompt
        entity.scheduledTime = order.scheduledTime
        entity.frequencyType = order.frequency.typeString
        entity.frequencyCustomMinutes = Int16(order.frequency.customMinutes ?? 0)
        entity.resources = order.resources.map { $0.rawValue } as NSArray
        entity.orderStatus = order.orderStatus.rawValue
        entity.createdAt = order.createdAt
        entity.updatedAt = order.updatedAt
        entity.needsSync = false

        try viewContext.save()
    }

    /// Update an existing order in local cache
    private func updateOrderInCache(_ order: Order) throws {
        let fetchRequest = OrderEntity.fetchRequest()
        fetchRequest.predicate = NSPredicate(format: "id == %@", order.id as CVarArg)

        if let entity = try viewContext.fetch(fetchRequest).first {
            entity.update(from: order)
            entity.needsSync = false
            try viewContext.save()
        } else {
            // Order doesn't exist locally, create it
            try saveOrderToCache(order)
        }
    }

    /// Delete an order from local cache
    private func deleteOrderFromCache(_ orderId: UUID) throws {
        let fetchRequest = OrderEntity.fetchRequest()
        fetchRequest.predicate = NSPredicate(format: "id == %@", orderId as CVarArg)

        if let entity = try viewContext.fetch(fetchRequest).first {
            viewContext.delete(entity)
            try viewContext.save()
        }
    }

    /// Sync all orders to local cache (replaces local with backend data)
    private func syncOrdersToCache(_ orders: [Order]) throws {
        // Delete all existing orders
        let fetchRequest = OrderEntity.fetchRequest()
        let existingEntities = try viewContext.fetch(fetchRequest)
        for entity in existingEntities {
            viewContext.delete(entity)
        }

        // Create new entities from backend data
        for order in orders {
            let entity = OrderEntity(context: viewContext)
            entity.id = order.id
            entity.name = order.name
            entity.prompt = order.prompt
            entity.scheduledTime = order.scheduledTime
            entity.frequencyType = order.frequency.typeString
            entity.frequencyCustomMinutes = Int16(order.frequency.customMinutes ?? 0)
            entity.resources = order.resources.map { $0.rawValue } as NSArray
            entity.orderStatus = order.orderStatus.rawValue
            entity.createdAt = order.createdAt
            entity.updatedAt = order.updatedAt
            entity.needsSync = false
        }

        try viewContext.save()
    }
}

// MARK: - Mock Orders Service (for previews/testing)

final class MockOrdersService: OrdersServiceProtocol {
    var orders: [Order] = Order.mockOrders
    var recentExecutions: [OrderExecution] = []

    func createOrder(_ order: Order) async throws -> Order {
        orders.append(order)
        return order
    }

    func updateOrder(_ order: Order) async throws -> Order {
        if let index = orders.firstIndex(where: { $0.id == order.id }) {
            orders[index] = order
        }
        return order
    }

    func deleteOrder(_ orderId: UUID) async throws {
        orders.removeAll { $0.id == orderId }
    }

    func fetchOrders() async throws -> [Order] {
        return orders
    }

    func fetchRecentExecutions(limit: Int) async throws -> [OrderExecution] {
        return recentExecutions
    }

    func toggleOrderStatus(_ orderId: UUID) async throws -> Order {
        guard let index = orders.firstIndex(where: { $0.id == orderId }) else {
            throw OrdersError.notFound
        }

        let current = orders[index]
        let newStatus: OrderStatus = (current.orderStatus == .active) ? .inactive : .active

        let updated = Order(
            id: current.id,
            name: current.name,
            prompt: current.prompt,
            scheduledTime: current.scheduledTime,
            frequency: current.frequency,
            resources: current.resources,
            orderStatus: newStatus,
            lastExecution: current.lastExecution,
            createdAt: current.createdAt,
            updatedAt: Date()
        )

        orders[index] = updated
        return updated
    }

    func retryOrder(_ orderId: UUID) async throws {
        // Mock implementation - just create a success execution
        guard let index = orders.firstIndex(where: { $0.id == orderId }) else {
            throw OrdersError.notFound
        }

        let execution = OrderExecution(
            id: UUID(),
            orderId: orderId,
            timestamp: Date(),
            status: .success,
            hestiaRead: nil,
            fullResponse: "Mock execution completed successfully"
        )

        let current = orders[index]
        orders[index] = Order(
            id: current.id,
            name: current.name,
            prompt: current.prompt,
            scheduledTime: current.scheduledTime,
            frequency: current.frequency,
            resources: current.resources,
            orderStatus: current.orderStatus,
            lastExecution: execution,
            createdAt: current.createdAt,
            updatedAt: Date()
        )

        recentExecutions.insert(execution, at: 0)
    }

    func syncOrders() async throws {
        // Mock implementation - just return existing orders
    }
}

// MARK: - Orders Error

enum OrdersError: LocalizedError {
    case validationFailed([String])
    case notFound
    case executionFailed(String)

    var errorDescription: String? {
        switch self {
        case .validationFailed(let errors):
            return "Validation failed: \(errors.joined(separator: ", "))"
        case .notFound:
            return "Order not found"
        case .executionFailed(let reason):
            return "Execution failed: \(reason)"
        }
    }
}
