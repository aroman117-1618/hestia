import CoreData
import HestiaShared

@objc(AgentProfileEntity)
public class AgentProfileEntity: NSManagedObject {
    @NSManaged public var id: UUID
    @NSManaged public var name: String
    @NSManaged public var photoPath: String?
    @NSManaged public var instructions: String
    @NSManaged public var gradientColor1: String
    @NSManaged public var gradientColor2: String
    @NSManaged public var isDefault: Bool
    @NSManaged public var canBeDeleted: Bool
    @NSManaged public var slotIndex: Int16
    @NSManaged public var createdAt: Date
    @NSManaged public var updatedAt: Date
}

// MARK: - Fetch Requests

extension AgentProfileEntity {
    @nonobjc public class func fetchRequest() -> NSFetchRequest<AgentProfileEntity> {
        return NSFetchRequest<AgentProfileEntity>(entityName: "AgentProfileEntity")
    }

    /// Fetch all agent profiles sorted by slot index
    static func allProfilesRequest() -> NSFetchRequest<AgentProfileEntity> {
        let request = fetchRequest()
        request.sortDescriptors = [NSSortDescriptor(keyPath: \AgentProfileEntity.slotIndex, ascending: true)]
        return request
    }

    /// Fetch agent profile by slot index
    static func profileBySlotRequest(slot: Int16) -> NSFetchRequest<AgentProfileEntity> {
        let request = fetchRequest()
        request.predicate = NSPredicate(format: "slotIndex == %d", slot)
        request.fetchLimit = 1
        return request
    }
}

// MARK: - Conversion to Domain Model

extension AgentProfileEntity {
    /// Convert to domain AgentProfile model
    func toAgentProfile() -> AgentProfile {
        AgentProfile(
            id: id,
            name: name,
            photoPath: photoPath,
            instructions: instructions,
            gradientColor1: gradientColor1,
            gradientColor2: gradientColor2,
            isDefault: isDefault,
            canBeDeleted: canBeDeleted,
            createdAt: createdAt,
            updatedAt: updatedAt
        )
    }

    /// Update from domain AgentProfile model
    func update(from profile: AgentProfile) {
        name = profile.name
        photoPath = profile.photoPath
        instructions = profile.instructions
        gradientColor1 = profile.gradientColor1
        gradientColor2 = profile.gradientColor2
        updatedAt = Date()
    }

    /// Create from domain AgentProfile model
    static func create(from profile: AgentProfile, slotIndex: Int16, in context: NSManagedObjectContext) -> AgentProfileEntity {
        let entity = AgentProfileEntity(context: context)
        entity.id = profile.id
        entity.name = profile.name
        entity.photoPath = profile.photoPath
        entity.instructions = profile.instructions
        entity.gradientColor1 = profile.gradientColor1
        entity.gradientColor2 = profile.gradientColor2
        entity.isDefault = profile.isDefault
        entity.canBeDeleted = profile.canBeDeleted
        entity.slotIndex = slotIndex
        entity.createdAt = profile.createdAt
        entity.updatedAt = profile.updatedAt
        return entity
    }
}

@objc(AgentProfileSnapshotEntity)
public class AgentProfileSnapshotEntity: NSManagedObject {
    @NSManaged public var id: UUID
    @NSManaged public var agentProfileData: Data
    @NSManaged public var snapshotDate: Date
    @NSManaged public var reason: String
    @NSManaged public var originalAgentId: UUID
}

// MARK: - Fetch Requests

extension AgentProfileSnapshotEntity {
    @nonobjc public class func fetchRequest() -> NSFetchRequest<AgentProfileSnapshotEntity> {
        return NSFetchRequest<AgentProfileSnapshotEntity>(entityName: "AgentProfileSnapshotEntity")
    }

    /// Fetch snapshots for a specific agent, ordered by date descending
    static func snapshotsForAgentRequest(agentId: UUID) -> NSFetchRequest<AgentProfileSnapshotEntity> {
        let request = fetchRequest()
        request.predicate = NSPredicate(format: "originalAgentId == %@", agentId as CVarArg)
        request.sortDescriptors = [NSSortDescriptor(keyPath: \AgentProfileSnapshotEntity.snapshotDate, ascending: false)]
        return request
    }

    /// Fetch all deleted agents' snapshots (for recovery)
    static func deletedAgentsRequest() -> NSFetchRequest<AgentProfileSnapshotEntity> {
        let request = fetchRequest()
        request.predicate = NSPredicate(format: "reason == %@", "deleted")
        request.sortDescriptors = [NSSortDescriptor(keyPath: \AgentProfileSnapshotEntity.snapshotDate, ascending: false)]
        return request
    }
}

// MARK: - Conversion to Domain Model

extension AgentProfileSnapshotEntity {
    /// Convert to domain AgentProfileSnapshot model
    func toAgentProfileSnapshot() -> AgentProfileSnapshot? {
        guard let profile = try? JSONDecoder().decode(AgentProfile.self, from: agentProfileData),
              let snapshotReason = SnapshotReason(rawValue: reason) else {
            return nil
        }

        return AgentProfileSnapshot(
            agentProfile: profile,
            snapshotDate: snapshotDate,
            reason: snapshotReason
        )
    }

    /// Create snapshot from agent profile
    static func create(from profile: AgentProfile, reason: SnapshotReason, in context: NSManagedObjectContext) -> AgentProfileSnapshotEntity? {
        guard let data = try? JSONEncoder().encode(profile) else { return nil }

        let entity = AgentProfileSnapshotEntity(context: context)
        entity.id = UUID()
        entity.agentProfileData = data
        entity.snapshotDate = Date()
        entity.reason = reason.rawValue
        entity.originalAgentId = profile.id
        return entity
    }
}

@objc(UserProfileEntity)
public class UserProfileEntity: NSManagedObject {
    @NSManaged public var id: UUID
    @NSManaged public var name: String
    @NSManaged public var userDescription: String?
    @NSManaged public var photoPath: String?
    @NSManaged public var pushNotificationsEnabled: Bool
    @NSManaged public var createdAt: Date
    @NSManaged public var updatedAt: Date
}

// MARK: - Fetch Requests

extension UserProfileEntity {
    @nonobjc public class func fetchRequest() -> NSFetchRequest<UserProfileEntity> {
        return NSFetchRequest<UserProfileEntity>(entityName: "UserProfileEntity")
    }

    /// Fetch the user profile (should only be one)
    static func userProfileRequest() -> NSFetchRequest<UserProfileEntity> {
        let request = fetchRequest()
        request.fetchLimit = 1
        return request
    }
}

// MARK: - Conversion to Domain Model

extension UserProfileEntity {
    /// Convert to domain UserProfile model
    func toUserProfile() -> UserProfile {
        UserProfile(
            name: name,
            description: userDescription,
            photoPath: photoPath,
            pushNotificationsEnabled: pushNotificationsEnabled
        )
    }

    /// Update from domain UserProfile model
    func update(from profile: UserProfile) {
        name = profile.name
        userDescription = profile.description
        photoPath = profile.photoPath
        pushNotificationsEnabled = profile.pushNotificationsEnabled
        updatedAt = Date()
    }

    /// Create from domain UserProfile model
    static func create(from profile: UserProfile, in context: NSManagedObjectContext) -> UserProfileEntity {
        let entity = UserProfileEntity(context: context)
        entity.id = UUID()
        entity.name = profile.name
        entity.userDescription = profile.description
        entity.photoPath = profile.photoPath
        entity.pushNotificationsEnabled = profile.pushNotificationsEnabled
        entity.createdAt = Date()
        entity.updatedAt = Date()
        return entity
    }
}
