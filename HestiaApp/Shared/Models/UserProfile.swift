import Foundation

/// User profile data
struct UserProfile: Codable, Equatable {
    var name: String
    var description: String?
    var photoPath: String?
    var pushNotificationsEnabled: Bool

    // MARK: - Defaults

    static let `default` = UserProfile(
        name: "Andrew",
        description: nil,
        photoPath: nil,
        pushNotificationsEnabled: true
    )

    // MARK: - Computed Properties

    /// First letter of name for avatar placeholder
    var initial: String {
        String(name.prefix(1)).uppercased()
    }

    /// Display name (first name only)
    var displayName: String {
        name.components(separatedBy: " ").first ?? name
    }
}
