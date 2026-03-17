import Foundation

/// User profile data
public struct UserProfile: Codable, Equatable, Sendable {
    public var name: String
    public var description: String?
    public var photoPath: String?
    public var pushNotificationsEnabled: Bool

    public init(name: String, description: String?, photoPath: String?, pushNotificationsEnabled: Bool) {
        self.name = name
        self.description = description
        self.photoPath = photoPath
        self.pushNotificationsEnabled = pushNotificationsEnabled
    }

    // MARK: - Defaults

    public static let `default` = UserProfile(
        name: "Andrew",
        description: nil,
        photoPath: nil,
        pushNotificationsEnabled: true
    )

    // MARK: - Computed Properties

    /// First letter of name for avatar placeholder
    public var initial: String {
        String(name.prefix(1)).uppercased()
    }

    /// Display name (first name only)
    public var displayName: String {
        name.components(separatedBy: " ").first ?? name
    }
}
