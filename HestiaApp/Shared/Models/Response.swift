import Foundation

/// Response from the Hestia backend
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
struct HestiaResponse: Codable {
    let requestId: String
    let content: String
    let responseType: ResponseType
    let mode: String
    let sessionId: String?
    let timestamp: Date
    let metrics: ResponseMetrics
    let toolCalls: [ToolCallInfo]?
    let error: ResponseError?
}

/// Type of response from the backend
enum ResponseType: String, Codable {
    case text
    case error
    case toolCall = "tool_call"
    case clarification
}

/// Performance metrics for a response
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
struct ResponseMetrics: Codable {
    let tokensIn: Int
    let tokensOut: Int
    let durationMs: Double
}

/// Error information from the backend
struct ResponseError: Codable {
    let code: String
    let message: String
}

/// Tool call information
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
struct ToolCallInfo: Codable, Identifiable {
    let id: String
    let toolName: String
    let arguments: [String: String]?
    let status: String?
    let result: String?
}

// MARK: - Request Model

/// Request to send to the Hestia backend
/// Note: Property names use camelCase; APIClient's encoder auto-converts to snake_case
struct HestiaRequest: Codable {
    let message: String
    let sessionId: String?
    let deviceId: String?
    let contextHints: [String: String]?
}

// MARK: - Device Registration

/// Response from device registration endpoint
/// Note: Uses automatic snake_case conversion from JSONDecoder
struct DeviceRegistrationResponse: Codable {
    let deviceId: String
    let token: String
    let expiresAt: String?
}

/// Request for device registration
/// Note: Uses automatic snake_case conversion from JSONEncoder
struct DeviceRegistrationRequest: Codable {
    let deviceName: String
    let deviceType: String
}
