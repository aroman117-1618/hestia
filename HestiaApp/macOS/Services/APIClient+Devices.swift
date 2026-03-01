import Foundation
import HestiaShared

private struct DeviceEmptyBody: Codable {}

/// Device management API methods (macOS duplicate).
extension APIClient {
    func getDevices() async throws -> DeviceListResponse {
        return try await get("/v1/user/devices")
    }

    func revokeDevice(_ deviceId: String) async throws -> DeviceRevokeResponse {
        let encoded = deviceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? deviceId
        return try await post("/v1/user/devices/\(encoded)/revoke", body: DeviceEmptyBody())
    }

    func unrevokeDevice(_ deviceId: String) async throws -> DeviceRevokeResponse {
        let encoded = deviceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? deviceId
        return try await post("/v1/user/devices/\(encoded)/unrevoke", body: DeviceEmptyBody())
    }
}
