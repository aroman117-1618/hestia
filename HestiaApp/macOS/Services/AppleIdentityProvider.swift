import Contacts
import AppKit

/// Fetches user identity from Apple ecosystem:
/// 1. Contacts "Me" card (preferred -- has photo + full name)
/// 2. macOS user account fallback (NSFullUserName -- no photo)
struct AppleIdentityProvider {

    struct UserIdentity {
        let fullName: String?
        let firstName: String?
        let photo: Data?
    }

    /// Fetch the user's identity from the Contacts "Me" card.
    /// Falls back to macOS username if Contacts is unavailable or denied.
    static func fetchIdentity() async -> UserIdentity {
        let store = CNContactStore()

        // Check authorization
        let status = CNContactStore.authorizationStatus(for: .contacts)

        if status == .notDetermined {
            do {
                let granted = try await store.requestAccess(for: .contacts)
                if !granted {
                    return fallbackIdentity()
                }
            } catch {
                return fallbackIdentity()
            }
        } else if status != .authorized {
            return fallbackIdentity()
        }

        // Try to fetch "Me" card
        let keysToFetch: [CNKeyDescriptor] = [
            CNContactGivenNameKey as CNKeyDescriptor,
            CNContactFamilyNameKey as CNKeyDescriptor,
            CNContactNicknameKey as CNKeyDescriptor,
            CNContactImageDataKey as CNKeyDescriptor,
            CNContactThumbnailImageDataKey as CNKeyDescriptor,
        ]

        if let meContact = try? store.unifiedMeContactWithKeys(toFetch: keysToFetch) {
            let fullName = [meContact.givenName, meContact.familyName]
                .filter { !$0.isEmpty }
                .joined(separator: " ")

            return UserIdentity(
                fullName: fullName.isEmpty ? nil : fullName,
                firstName: meContact.givenName.isEmpty ? nil : meContact.givenName,
                photo: meContact.thumbnailImageData ?? meContact.imageData
            )
        }

        return fallbackIdentity()
    }

    /// Fallback: use macOS login name
    private static func fallbackIdentity() -> UserIdentity {
        let name = NSFullUserName()
        let first = name.split(separator: " ").first.map(String.init)
        return UserIdentity(
            fullName: name.isEmpty ? nil : name,
            firstName: first,
            photo: nil
        )
    }
}
