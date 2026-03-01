import Foundation

// MARK: - Device Management API Types (macOS duplicate)

struct DeviceItem: Codable, Identifiable {
    let deviceId: String
    let deviceName: String
    let deviceType: String
    let registeredAt: String
    let lastSeenAt: String?
    let revokedAt: String?
    let isActive: Bool

    var id: String { deviceId }

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case deviceName = "device_name"
        case deviceType = "device_type"
        case registeredAt = "registered_at"
        case lastSeenAt = "last_seen_at"
        case revokedAt = "revoked_at"
        case isActive = "is_active"
    }

    var iconName: String {
        switch deviceType.lowercased() {
        case "ios", "iphone": return "iphone"
        case "macos", "mac": return "desktopcomputer"
        case "ipad": return "ipad"
        default: return "laptopcomputer"
        }
    }

    var lastSeenDisplay: String {
        guard let lastSeen = lastSeenAt else { return "Never" }
        guard let date = ISO8601DateFormatter().date(from: lastSeen) else { return lastSeen }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    var registeredDisplay: String {
        guard let date = ISO8601DateFormatter().date(from: registeredAt) else { return registeredAt }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }
}

struct DeviceListResponse: Codable {
    let devices: [DeviceItem]
    let count: Int
}

struct DeviceRevokeResponse: Codable {
    let deviceId: String
    let revoked: Bool
    let message: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case revoked, message
    }
}
