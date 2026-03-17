import Foundation

/// Response from the Hestia backend
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
public struct HestiaResponse: Codable, Sendable {
    public let requestId: String
    public let content: String
    public let responseType: ResponseType
    public let mode: String
    public let sessionId: String?
    public let timestamp: Date
    public let metrics: ResponseMetrics
    public let toolCalls: [ToolCallInfo]?
    public let error: ResponseError?
    public let bylines: [AgentByline]?

    public init(requestId: String, content: String, responseType: ResponseType, mode: String, sessionId: String?, timestamp: Date, metrics: ResponseMetrics, toolCalls: [ToolCallInfo]?, error: ResponseError?, bylines: [AgentByline]? = nil) {
        self.requestId = requestId
        self.content = content
        self.responseType = responseType
        self.mode = mode
        self.sessionId = sessionId
        self.timestamp = timestamp
        self.metrics = metrics
        self.toolCalls = toolCalls
        self.error = error
        self.bylines = bylines
    }
}

/// Type of response from the backend
public enum ResponseType: String, Codable, Sendable {
    case text
    case error
    case toolCall = "tool_call"
    case clarification
}

/// Performance metrics for a response
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
public struct ResponseMetrics: Codable, Sendable {
    public let tokensIn: Int
    public let tokensOut: Int
    public let durationMs: Double

    public init(tokensIn: Int, tokensOut: Int, durationMs: Double) {
        self.tokensIn = tokensIn
        self.tokensOut = tokensOut
        self.durationMs = durationMs
    }
}

/// Error information from the backend
public struct ResponseError: Codable, Sendable {
    public let code: String
    public let message: String

    public init(code: String, message: String) {
        self.code = code
        self.message = message
    }
}

/// Tool call information
/// Note: Property names use camelCase; APIClient's decoder auto-converts from snake_case
public struct ToolCallInfo: Codable, Identifiable, Sendable {
    public let id: String
    public let toolName: String
    public let arguments: [String: String]?
    public let status: String?
    public let result: String?

    public init(id: String, toolName: String, arguments: [String: String]?, status: String?, result: String?) {
        self.id = id
        self.toolName = toolName
        self.arguments = arguments
        self.status = status
        self.result = result
    }
}

// MARK: - Agent Byline Attribution (ADR-042)

/// Attribution for a specialist agent's contribution to a response
public struct AgentByline: Codable, Sendable, Equatable {
    public let agent: String       // "artemis", "apollo"
    public let contribution: String // "analysis", "implementation"
    public let summary: String     // One-line description

    public init(agent: String, contribution: String, summary: String) {
        self.agent = agent
        self.contribution = contribution
        self.summary = summary
    }

    /// Display icon for this agent
    public var icon: String {
        switch agent {
        case "artemis": return "\u{1F4D0}"  // 📐
        case "apollo": return "\u{26A1}"    // ⚡
        default: return ""
        }
    }

    /// Display name for this agent
    public var displayName: String {
        switch agent {
        case "artemis": return "Artemis"
        case "apollo": return "Apollo"
        default: return agent.capitalized
        }
    }

    /// Formatted single-line byline
    public var formatted: String {
        "\(icon) \(displayName) \u{2014} \(summary)"
    }
}

// MARK: - SSE Streaming Events

/// Events received from the SSE streaming chat endpoint (POST /v1/chat/stream).
/// Each event corresponds to a stage in the Hestia response pipeline.
public enum ChatStreamEvent: Sendable {
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
    /// Reasoning/decision event — shows pipeline decisions in real-time
    case reasoning(aspect: String, summary: String, content: String?)
    /// Final event — contains metrics, mode, session ID, optional bylines
    case done(requestId: String, metrics: ResponseMetrics?, mode: String, sessionId: String?, bylines: [AgentByline]?)
    /// Error during processing
    case error(code: String, message: String)
}

/// Parse an SSE event from its type string and JSON data string.
/// Returns nil for unrecognized event types (forward-compatible).
public func parseChatStreamEvent(type: String, data: String) -> ChatStreamEvent? {
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

    case "reasoning":
        let aspect = dict["aspect"] as? String ?? ""
        let summary = dict["summary"] as? String ?? ""
        let content = dict["content"] as? String
        return .reasoning(aspect: aspect, summary: summary, content: content)

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
        var bylines: [AgentByline]?
        if let bylineArray = dict["bylines"] as? [[String: Any]] {
            bylines = bylineArray.compactMap { item in
                guard let agent = item["agent"] as? String,
                      let contribution = item["contribution"] as? String,
                      let summary = item["summary"] as? String else { return nil }
                return AgentByline(agent: agent, contribution: contribution, summary: summary)
            }
            if bylines?.isEmpty == true { bylines = nil }
        }
        return .done(requestId: requestId, metrics: metrics, mode: mode, sessionId: sessionId, bylines: bylines)

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
public struct HestiaRequest: Codable, Sendable {
    public let message: String
    public let sessionId: String?
    public let deviceId: String?
    public let forceLocal: Bool
    public let contextHints: [String: String]?

    public init(message: String, sessionId: String?, deviceId: String?, forceLocal: Bool, contextHints: [String: String]?) {
        self.message = message
        self.sessionId = sessionId
        self.deviceId = deviceId
        self.forceLocal = forceLocal
        self.contextHints = contextHints
    }
}

// MARK: - Device Registration

/// Response from device registration endpoint
/// Note: Uses automatic snake_case conversion from JSONDecoder
public struct DeviceRegistrationResponse: Codable, Sendable {
    public let deviceId: String
    public let token: String
    public let expiresAt: String?

    public init(deviceId: String, token: String, expiresAt: String?) {
        self.deviceId = deviceId
        self.token = token
        self.expiresAt = expiresAt
    }
}

/// Request for device registration
/// Note: Uses automatic snake_case conversion from JSONEncoder
public struct DeviceRegistrationRequest: Codable, Sendable {
    public let deviceName: String
    public let deviceType: String

    public init(deviceName: String, deviceType: String) {
        self.deviceName = deviceName
        self.deviceType = deviceType
    }
}

// MARK: - Invite-Based Onboarding

/// Request to register using an invite token from QR code
public struct InviteRegisterRequest: Codable, Sendable {
    public let inviteToken: String
    public let deviceName: String?
    public let deviceType: String?

    public init(inviteToken: String, deviceName: String?, deviceType: String?) {
        self.inviteToken = inviteToken
        self.deviceName = deviceName
        self.deviceType = deviceType
    }
}

/// Response from invite-based registration
public struct InviteRegisterResponse: Codable, Sendable {
    public let deviceId: String
    public let token: String
    public let expiresAt: String?
    public let serverUrl: String

    public init(deviceId: String, token: String, expiresAt: String?, serverUrl: String) {
        self.deviceId = deviceId
        self.token = token
        self.expiresAt = expiresAt
        self.serverUrl = serverUrl
    }
}

/// Parsed QR code payload from invite generation
public struct QRInvitePayload: Codable, Sendable {
    /// Invite JWT token
    public let t: String
    /// Server base URL
    public let u: String
    /// TLS certificate SHA-256 fingerprint
    public let f: String

    public init(t: String, u: String, f: String) {
        self.t = t
        self.u = u
        self.f = f
    }
}
