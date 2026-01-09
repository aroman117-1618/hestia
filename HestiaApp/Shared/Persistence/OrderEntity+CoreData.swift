import CoreData

@objc(OrderEntity)
public class OrderEntity: NSManagedObject {
    @NSManaged public var id: UUID
    @NSManaged public var name: String
    @NSManaged public var prompt: String
    @NSManaged public var scheduledTime: Date
    @NSManaged public var frequencyType: String
    @NSManaged public var frequencyCustomMinutes: Int16
    @NSManaged public var resources: NSArray
    @NSManaged public var orderStatus: String
    @NSManaged public var createdAt: Date
    @NSManaged public var updatedAt: Date
    @NSManaged public var executions: NSSet?
    @NSManaged public var needsSync: Bool  // Flag for offline sync tracking
}

// MARK: - Fetch Requests

extension OrderEntity {
    @nonobjc public class func fetchRequest() -> NSFetchRequest<OrderEntity> {
        return NSFetchRequest<OrderEntity>(entityName: "OrderEntity")
    }

    /// Fetch all orders sorted by scheduled time
    static func allOrdersRequest() -> NSFetchRequest<OrderEntity> {
        let request = fetchRequest()
        request.sortDescriptors = [NSSortDescriptor(keyPath: \OrderEntity.scheduledTime, ascending: true)]
        return request
    }

    /// Fetch active orders only
    static func activeOrdersRequest() -> NSFetchRequest<OrderEntity> {
        let request = fetchRequest()
        request.predicate = NSPredicate(format: "orderStatus == %@", "active")
        request.sortDescriptors = [NSSortDescriptor(keyPath: \OrderEntity.scheduledTime, ascending: true)]
        return request
    }
}

// MARK: - Generated accessors for executions

extension OrderEntity {
    @objc(addExecutionsObject:)
    @NSManaged public func addToExecutions(_ value: OrderExecutionEntity)

    @objc(removeExecutionsObject:)
    @NSManaged public func removeFromExecutions(_ value: OrderExecutionEntity)

    @objc(addExecutions:)
    @NSManaged public func addToExecutions(_ values: NSSet)

    @objc(removeExecutions:)
    @NSManaged public func removeFromExecutions(_ values: NSSet)
}

// MARK: - Conversion to Domain Model

extension OrderEntity {
    /// Convert to domain Order model
    func toOrder() -> Order {
        let resourceStrings = resources as? [String] ?? []
        let mcpResources = Set(resourceStrings.compactMap { MCPResource(rawValue: $0) })

        return Order(
            id: id,
            name: name,
            prompt: prompt,
            scheduledTime: scheduledTime,
            frequency: OrderFrequency.from(type: frequencyType, customMinutes: Int(frequencyCustomMinutes)),
            resources: mcpResources,
            orderStatus: OrderStatus(rawValue: orderStatus) ?? .active,
            lastExecution: lastExecutionEntity?.toOrderExecution(),
            createdAt: createdAt,
            updatedAt: updatedAt
        )
    }

    /// Get the most recent execution
    var lastExecutionEntity: OrderExecutionEntity? {
        guard let executionsSet = executions as? Set<OrderExecutionEntity> else { return nil }
        return executionsSet.sorted { $0.timestamp > $1.timestamp }.first
    }

    /// Update from domain Order model
    func update(from order: Order) {
        name = order.name
        prompt = order.prompt
        scheduledTime = order.scheduledTime
        frequencyType = order.frequency.typeString
        frequencyCustomMinutes = Int16(order.frequency.customMinutes ?? 0)
        resources = order.resources.map { $0.rawValue } as NSArray
        orderStatus = order.orderStatus.rawValue
        updatedAt = Date()
    }
}

@objc(OrderExecutionEntity)
public class OrderExecutionEntity: NSManagedObject {
    @NSManaged public var id: UUID
    @NSManaged public var timestamp: Date
    @NSManaged public var status: String
    @NSManaged public var hestiaRead: String?
    @NSManaged public var fullResponse: String?
    @NSManaged public var order: OrderEntity
}

// MARK: - Fetch Requests

extension OrderExecutionEntity {
    @nonobjc public class func fetchRequest() -> NSFetchRequest<OrderExecutionEntity> {
        return NSFetchRequest<OrderExecutionEntity>(entityName: "OrderExecutionEntity")
    }

    /// Fetch executions for a specific order within the last 48 hours
    static func recentExecutionsRequest(forOrderId orderId: UUID) -> NSFetchRequest<OrderExecutionEntity> {
        let request = fetchRequest()
        let cutoff = Calendar.current.date(byAdding: .hour, value: -48, to: Date()) ?? Date()
        request.predicate = NSPredicate(format: "order.id == %@ AND timestamp >= %@", orderId as CVarArg, cutoff as NSDate)
        request.sortDescriptors = [NSSortDescriptor(keyPath: \OrderExecutionEntity.timestamp, ascending: false)]
        return request
    }

    /// Fetch all recent executions (last 48 hours) across all orders
    static func allRecentExecutionsRequest() -> NSFetchRequest<OrderExecutionEntity> {
        let request = fetchRequest()
        let cutoff = Calendar.current.date(byAdding: .hour, value: -48, to: Date()) ?? Date()
        request.predicate = NSPredicate(format: "timestamp >= %@", cutoff as NSDate)
        request.sortDescriptors = [NSSortDescriptor(keyPath: \OrderExecutionEntity.timestamp, ascending: false)]
        return request
    }
}

// MARK: - Conversion to Domain Model

extension OrderExecutionEntity {
    /// Convert to domain OrderExecution model
    func toOrderExecution() -> OrderExecution {
        OrderExecution(
            id: id,
            orderId: order.id,
            timestamp: timestamp,
            status: ExecutionStatus(rawValue: status) ?? .scheduled,
            hestiaRead: hestiaRead,
            fullResponse: fullResponse
        )
    }

    /// Create from domain OrderExecution model
    static func create(from execution: OrderExecution, order: OrderEntity, in context: NSManagedObjectContext) -> OrderExecutionEntity {
        let entity = OrderExecutionEntity(context: context)
        entity.id = execution.id
        entity.timestamp = execution.timestamp
        entity.status = execution.status.rawValue
        entity.hestiaRead = execution.hestiaRead
        entity.fullResponse = execution.fullResponse
        entity.order = order
        return entity
    }
}
