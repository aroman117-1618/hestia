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

// MARK: - SSE Streaming Events

/// Events received from the SSE streaming chat endpoint (POST /v1/chat/stream).
/// Each event corresponds to a stage in the Hestia response pipeline.
enum ChatStreamEvent {
    /// Pipeline progress update (preparing, inference, tools)
    case status(stage: String, detail: String)
    /// Streaming response token — append to the live message
    case token(content: String, requestId: String)
    /// Tool execution completed
    case toolResult(callId: String, toolName: String, status: String, result: String?)
    /// Signal to discard previously streamed tokens (tool re-synthesis)
    case clearStream
    /// Metadata insight (cloud routing, synthesis info)
    case insight(content: String, key: String)
    /// Final event — contains metrics, mode, session ID
    case done(requestId: String, metrics: ResponseMetrics?, mode: String, sessionId: String?)
    /// Error during processing
    case error(code: String, message: String)
}

/// Parse an SSE event from its type string and JSON data string.
/// Returns nil for unrecognized event types (forward-compatible).
func parseChatStreamEvent(type: String, data: String) -> ChatStreamEvent? {
    guard let jsonData = data.data(using: .utf8),
          let dict = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else {
        return nil
    }

    switch type {
    case "status":
        guard let stage = dict["stage"] as? String,
              let detail = dict["detail"] as? String else { return nil }
        return .status(stage: stage, detail: detail)

    case "token":
        guard let content = dict["content"] as? String,
              let requestId = dict["request_id"] as? String else { return nil }
        return .token(content: content, requestId: requestId)

    case "tool_result":
        guard let callId = dict["call_id"] as? String,
              let toolName = dict["tool_name"] as? String,
              let status = dict["status"] as? String else { return nil }
        let result = dict["result"] as? String
        return .toolResult(callId: callId, toolName: toolName, status: status, result: result)

    case "clear_stream":
        return .clearStream

    case "insight":
        guard let content = dict["content"] as? String,
              let key = dict["insight_key"] as? String else { return nil }
        return .insight(content: content, key: key)

    case "done":
        let requestId = dict["request_id"] as? String ?? ""
        let mode = dict["mode"] as? String ?? "tia"
        let sessionId = dict["session_id"] as? String
        var metrics: ResponseMetrics?
        if let metricsDict = dict["metrics"] as? [String: Any] {
            let tokensIn = metricsDict["tokens_in"] as? Int ?? 0
            let tokensOut = metricsDict["tokens_out"] as? Int ?? 0
            let durationMs = metricsDict["duration_ms"] as? Double ?? 0
            metrics = ResponseMetrics(tokensIn: tokensIn, tokensOut: tokensOut, durationMs: durationMs)
        }
        return .done(requestId: requestId, metrics: metrics, mode: mode, sessionId: sessionId)

    case "error":
        let code = dict["code"] as? String ?? "unknown"
        let message = dict["message"] as? String ?? "An error occurred."
        return .error(code: code, message: message)

    default:
        return nil  // Forward-compatible: ignore unknown event types
    }
}

// MARK: - Request Model

/// Request to send to the Hestia backend
/// Note: Property names use camelCase; APIClient's encoder auto-converts to snake_case
struct HestiaRequest: Codable {
    let message: String
    let sessionId: String?
    let deviceId: String?
    let forceLocal: Bool
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

// MARK: - Invite-Based Onboarding

/// Request to register using an invite token from QR code
struct InviteRegisterRequest: Codable {
    let inviteToken: String
    let deviceName: String?
    let deviceType: String?
}

/// Response from invite-based registration
struct InviteRegisterResponse: Codable {
    let deviceId: String
    let token: String
    let expiresAt: String?
    let serverUrl: String
}

/// Parsed QR code payload from invite generation
struct QRInvitePayload: Codable {
    /// Invite JWT token
    let t: String
    /// Server base URL
    let u: String
    /// TLS certificate SHA-256 fingerprint
    let f: String
}
