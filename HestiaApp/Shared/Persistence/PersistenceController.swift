import CoreData

/// Core Data persistence controller for HestiaApp
final class PersistenceController: @unchecked Sendable {
    // MARK: - Shared Instance

    static let shared = PersistenceController()

    /// Preview instance for SwiftUI previews
    static let preview: PersistenceController = {
        let controller = PersistenceController(inMemory: true)
        // Add sample data for previews
        let context = controller.container.viewContext

        // Sample agent profiles
        let tiaProfile = AgentProfileEntity(context: context)
        tiaProfile.id = UUID()
        tiaProfile.name = "Tia"
        tiaProfile.instructions = "Efficient, competent, occasionally sardonic. Daily operations focus."
        tiaProfile.gradientColor1 = "E0A050"
        tiaProfile.gradientColor2 = "8B3A0F"
        tiaProfile.isDefault = true
        tiaProfile.canBeDeleted = false
        tiaProfile.slotIndex = 0
        tiaProfile.createdAt = Date()
        tiaProfile.updatedAt = Date()

        // Sample order
        let sampleOrder = OrderEntity(context: context)
        sampleOrder.id = UUID()
        sampleOrder.name = "Morning Brief"
        sampleOrder.prompt = "Summarize today's calendar, important emails, and any breaking news relevant to my interests."
        sampleOrder.scheduledTime = Calendar.current.date(bySettingHour: 7, minute: 30, second: 0, of: Date()) ?? Date()
        sampleOrder.frequencyType = "daily"
        sampleOrder.resources = ["calendar", "email", "firecrawl"] as NSArray
        sampleOrder.orderStatus = "active"
        sampleOrder.createdAt = Date()
        sampleOrder.updatedAt = Date()

        do {
            try context.save()
        } catch {
            print("Preview data creation failed: \(error)")
        }

        return controller
    }()

    // MARK: - Core Data Stack

    let container: NSPersistentContainer

    /// Main view context
    var viewContext: NSManagedObjectContext {
        container.viewContext
    }

    // MARK: - Initialization

    init(inMemory: Bool = false) {
        // Create the managed object model programmatically
        container = NSPersistentContainer(name: "HestiaDataModel", managedObjectModel: Self.createManagedObjectModel())

        if inMemory {
            container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
        }

        container.loadPersistentStores { description, error in
            if let error = error as NSError? {
                // In production, handle this gracefully
                print("Core Data failed to load: \(error), \(error.userInfo)")
            }
        }

        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergePolicy.mergeByPropertyObjectTrump
    }

    // MARK: - Managed Object Model (Programmatic)

    private static func createManagedObjectModel() -> NSManagedObjectModel {
        let model = NSManagedObjectModel()

        // OrderEntity
        let orderEntity = createOrderEntity()

        // OrderExecutionEntity
        let executionEntity = createOrderExecutionEntity()

        // AgentProfileEntity
        let agentEntity = createAgentProfileEntity()

        // AgentProfileSnapshotEntity
        let snapshotEntity = createAgentProfileSnapshotEntity()

        // UserProfileEntity
        let userEntity = createUserProfileEntity()

        // Set up relationships
        setupOrderRelationships(orderEntity: orderEntity, executionEntity: executionEntity)

        model.entities = [orderEntity, executionEntity, agentEntity, snapshotEntity, userEntity]
        return model
    }

    private static func createOrderEntity() -> NSEntityDescription {
        let entity = NSEntityDescription()
        entity.name = "OrderEntity"
        entity.managedObjectClassName = "OrderEntity"

        let idAttr = NSAttributeDescription()
        idAttr.name = "id"
        idAttr.attributeType = .UUIDAttributeType
        idAttr.isOptional = false

        let nameAttr = NSAttributeDescription()
        nameAttr.name = "name"
        nameAttr.attributeType = .stringAttributeType
        nameAttr.isOptional = false

        let promptAttr = NSAttributeDescription()
        promptAttr.name = "prompt"
        promptAttr.attributeType = .stringAttributeType
        promptAttr.isOptional = false

        let scheduledTimeAttr = NSAttributeDescription()
        scheduledTimeAttr.name = "scheduledTime"
        scheduledTimeAttr.attributeType = .dateAttributeType
        scheduledTimeAttr.isOptional = false

        let frequencyTypeAttr = NSAttributeDescription()
        frequencyTypeAttr.name = "frequencyType"
        frequencyTypeAttr.attributeType = .stringAttributeType
        frequencyTypeAttr.isOptional = false

        let frequencyCustomMinutesAttr = NSAttributeDescription()
        frequencyCustomMinutesAttr.name = "frequencyCustomMinutes"
        frequencyCustomMinutesAttr.attributeType = .integer16AttributeType
        frequencyCustomMinutesAttr.isOptional = true

        let resourcesAttr = NSAttributeDescription()
        resourcesAttr.name = "resources"
        resourcesAttr.attributeType = .transformableAttributeType
        resourcesAttr.valueTransformerName = "NSSecureUnarchiveFromData"
        resourcesAttr.isOptional = false

        let orderStatusAttr = NSAttributeDescription()
        orderStatusAttr.name = "orderStatus"
        orderStatusAttr.attributeType = .stringAttributeType
        orderStatusAttr.isOptional = false

        let createdAtAttr = NSAttributeDescription()
        createdAtAttr.name = "createdAt"
        createdAtAttr.attributeType = .dateAttributeType
        createdAtAttr.isOptional = false

        let updatedAtAttr = NSAttributeDescription()
        updatedAtAttr.name = "updatedAt"
        updatedAtAttr.attributeType = .dateAttributeType
        updatedAtAttr.isOptional = false

        let needsSyncAttr = NSAttributeDescription()
        needsSyncAttr.name = "needsSync"
        needsSyncAttr.attributeType = .booleanAttributeType
        needsSyncAttr.isOptional = false
        needsSyncAttr.defaultValue = false

        entity.properties = [
            idAttr, nameAttr, promptAttr, scheduledTimeAttr,
            frequencyTypeAttr, frequencyCustomMinutesAttr, resourcesAttr,
            orderStatusAttr, createdAtAttr, updatedAtAttr, needsSyncAttr
        ]

        return entity
    }

    private static func createOrderExecutionEntity() -> NSEntityDescription {
        let entity = NSEntityDescription()
        entity.name = "OrderExecutionEntity"
        entity.managedObjectClassName = "OrderExecutionEntity"

        let idAttr = NSAttributeDescription()
        idAttr.name = "id"
        idAttr.attributeType = .UUIDAttributeType
        idAttr.isOptional = false

        let timestampAttr = NSAttributeDescription()
        timestampAttr.name = "timestamp"
        timestampAttr.attributeType = .dateAttributeType
        timestampAttr.isOptional = false

        let statusAttr = NSAttributeDescription()
        statusAttr.name = "status"
        statusAttr.attributeType = .stringAttributeType
        statusAttr.isOptional = false

        let hestiaReadAttr = NSAttributeDescription()
        hestiaReadAttr.name = "hestiaRead"
        hestiaReadAttr.attributeType = .stringAttributeType
        hestiaReadAttr.isOptional = true

        let fullResponseAttr = NSAttributeDescription()
        fullResponseAttr.name = "fullResponse"
        fullResponseAttr.attributeType = .stringAttributeType
        fullResponseAttr.isOptional = true

        entity.properties = [idAttr, timestampAttr, statusAttr, hestiaReadAttr, fullResponseAttr]

        return entity
    }

    private static func createAgentProfileEntity() -> NSEntityDescription {
        let entity = NSEntityDescription()
        entity.name = "AgentProfileEntity"
        entity.managedObjectClassName = "AgentProfileEntity"

        let idAttr = NSAttributeDescription()
        idAttr.name = "id"
        idAttr.attributeType = .UUIDAttributeType
        idAttr.isOptional = false

        let nameAttr = NSAttributeDescription()
        nameAttr.name = "name"
        nameAttr.attributeType = .stringAttributeType
        nameAttr.isOptional = false

        let photoPathAttr = NSAttributeDescription()
        photoPathAttr.name = "photoPath"
        photoPathAttr.attributeType = .stringAttributeType
        photoPathAttr.isOptional = true

        let instructionsAttr = NSAttributeDescription()
        instructionsAttr.name = "instructions"
        instructionsAttr.attributeType = .stringAttributeType
        instructionsAttr.isOptional = false

        let gradientColor1Attr = NSAttributeDescription()
        gradientColor1Attr.name = "gradientColor1"
        gradientColor1Attr.attributeType = .stringAttributeType
        gradientColor1Attr.isOptional = false

        let gradientColor2Attr = NSAttributeDescription()
        gradientColor2Attr.name = "gradientColor2"
        gradientColor2Attr.attributeType = .stringAttributeType
        gradientColor2Attr.isOptional = false

        let isDefaultAttr = NSAttributeDescription()
        isDefaultAttr.name = "isDefault"
        isDefaultAttr.attributeType = .booleanAttributeType
        isDefaultAttr.isOptional = false
        isDefaultAttr.defaultValue = false

        let canBeDeletedAttr = NSAttributeDescription()
        canBeDeletedAttr.name = "canBeDeleted"
        canBeDeletedAttr.attributeType = .booleanAttributeType
        canBeDeletedAttr.isOptional = false
        canBeDeletedAttr.defaultValue = true

        let slotIndexAttr = NSAttributeDescription()
        slotIndexAttr.name = "slotIndex"
        slotIndexAttr.attributeType = .integer16AttributeType
        slotIndexAttr.isOptional = false

        let createdAtAttr = NSAttributeDescription()
        createdAtAttr.name = "createdAt"
        createdAtAttr.attributeType = .dateAttributeType
        createdAtAttr.isOptional = false

        let updatedAtAttr = NSAttributeDescription()
        updatedAtAttr.name = "updatedAt"
        updatedAtAttr.attributeType = .dateAttributeType
        updatedAtAttr.isOptional = false

        entity.properties = [
            idAttr, nameAttr, photoPathAttr, instructionsAttr,
            gradientColor1Attr, gradientColor2Attr, isDefaultAttr,
            canBeDeletedAttr, slotIndexAttr, createdAtAttr, updatedAtAttr
        ]

        return entity
    }

    private static func createAgentProfileSnapshotEntity() -> NSEntityDescription {
        let entity = NSEntityDescription()
        entity.name = "AgentProfileSnapshotEntity"
        entity.managedObjectClassName = "AgentProfileSnapshotEntity"

        let idAttr = NSAttributeDescription()
        idAttr.name = "id"
        idAttr.attributeType = .UUIDAttributeType
        idAttr.isOptional = false

        let agentProfileDataAttr = NSAttributeDescription()
        agentProfileDataAttr.name = "agentProfileData"
        agentProfileDataAttr.attributeType = .binaryDataAttributeType
        agentProfileDataAttr.isOptional = false

        let snapshotDateAttr = NSAttributeDescription()
        snapshotDateAttr.name = "snapshotDate"
        snapshotDateAttr.attributeType = .dateAttributeType
        snapshotDateAttr.isOptional = false

        let reasonAttr = NSAttributeDescription()
        reasonAttr.name = "reason"
        reasonAttr.attributeType = .stringAttributeType
        reasonAttr.isOptional = false

        let originalAgentIdAttr = NSAttributeDescription()
        originalAgentIdAttr.name = "originalAgentId"
        originalAgentIdAttr.attributeType = .UUIDAttributeType
        originalAgentIdAttr.isOptional = false

        entity.properties = [idAttr, agentProfileDataAttr, snapshotDateAttr, reasonAttr, originalAgentIdAttr]

        return entity
    }

    private static func createUserProfileEntity() -> NSEntityDescription {
        let entity = NSEntityDescription()
        entity.name = "UserProfileEntity"
        entity.managedObjectClassName = "UserProfileEntity"

        let idAttr = NSAttributeDescription()
        idAttr.name = "id"
        idAttr.attributeType = .UUIDAttributeType
        idAttr.isOptional = false

        let nameAttr = NSAttributeDescription()
        nameAttr.name = "name"
        nameAttr.attributeType = .stringAttributeType
        nameAttr.isOptional = false

        let descriptionAttr = NSAttributeDescription()
        descriptionAttr.name = "userDescription"
        descriptionAttr.attributeType = .stringAttributeType
        descriptionAttr.isOptional = true

        let photoPathAttr = NSAttributeDescription()
        photoPathAttr.name = "photoPath"
        photoPathAttr.attributeType = .stringAttributeType
        photoPathAttr.isOptional = true

        let pushNotificationsEnabledAttr = NSAttributeDescription()
        pushNotificationsEnabledAttr.name = "pushNotificationsEnabled"
        pushNotificationsEnabledAttr.attributeType = .booleanAttributeType
        pushNotificationsEnabledAttr.isOptional = false
        pushNotificationsEnabledAttr.defaultValue = true

        let createdAtAttr = NSAttributeDescription()
        createdAtAttr.name = "createdAt"
        createdAtAttr.attributeType = .dateAttributeType
        createdAtAttr.isOptional = false

        let updatedAtAttr = NSAttributeDescription()
        updatedAtAttr.name = "updatedAt"
        updatedAtAttr.attributeType = .dateAttributeType
        updatedAtAttr.isOptional = false

        entity.properties = [
            idAttr, nameAttr, descriptionAttr, photoPathAttr,
            pushNotificationsEnabledAttr, createdAtAttr, updatedAtAttr
        ]

        return entity
    }

    private static func setupOrderRelationships(orderEntity: NSEntityDescription, executionEntity: NSEntityDescription) {
        // Order -> Executions (one-to-many)
        let executionsRelation = NSRelationshipDescription()
        executionsRelation.name = "executions"
        executionsRelation.destinationEntity = executionEntity
        executionsRelation.isOptional = true
        executionsRelation.deleteRule = .cascadeDeleteRule
        executionsRelation.maxCount = 0 // unlimited
        executionsRelation.minCount = 0

        // Execution -> Order (many-to-one)
        let orderRelation = NSRelationshipDescription()
        orderRelation.name = "order"
        orderRelation.destinationEntity = orderEntity
        orderRelation.isOptional = false
        orderRelation.deleteRule = .nullifyDeleteRule
        orderRelation.maxCount = 1
        orderRelation.minCount = 1

        // Set inverse relationships
        executionsRelation.inverseRelationship = orderRelation
        orderRelation.inverseRelationship = executionsRelation

        // Add relationships to entities
        orderEntity.properties.append(executionsRelation)
        executionEntity.properties.append(orderRelation)
    }

    // MARK: - Convenience Methods

    /// Save the view context
    func save() {
        let context = viewContext
        guard context.hasChanges else { return }

        do {
            try context.save()
        } catch {
            print("Failed to save context: \(error)")
        }
    }

    /// Create a new background context
    func newBackgroundContext() -> NSManagedObjectContext {
        container.newBackgroundContext()
    }

    /// Perform cleanup of old agent profile snapshots (older than 90 days)
    func cleanupOldSnapshots() async {
        let context = newBackgroundContext()
        let cutoffDate = Calendar.current.date(byAdding: .day, value: -90, to: Date()) ?? Date()

        await context.perform {
            let request = NSFetchRequest<NSManagedObject>(entityName: "AgentProfileSnapshotEntity")
            request.predicate = NSPredicate(format: "snapshotDate < %@", cutoffDate as NSDate)

            do {
                let oldSnapshots = try context.fetch(request)
                for snapshot in oldSnapshots {
                    context.delete(snapshot)
                }
                if context.hasChanges {
                    try context.save()
                }
            } catch {
                print("Failed to cleanup old snapshots: \(error)")
            }
        }
    }
}
