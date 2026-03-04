import Foundation

// MARK: - Outcome Response

/// A single outcome record from the backend.
struct OutcomeResponse: Codable, Identifiable {
    let id: String
    let sessionId: String?
    let messageId: String?
    let responseType: String?
    let durationMs: Int?
    let feedback: String?
    let feedbackNote: String?
    let implicitSignal: String?
    let elapsedToNextMs: Int?
    let timestamp: String?
    let metadata: [String: AnyCodableValue]?

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case messageId = "message_id"
        case responseType = "response_type"
        case durationMs = "duration_ms"
        case feedback
        case feedbackNote = "feedback_note"
        case implicitSignal = "implicit_signal"
        case elapsedToNextMs = "elapsed_to_next_ms"
        case timestamp
        case metadata
    }
}

// MARK: - Outcome List Response

/// Response from GET /v1/outcomes.
struct OutcomeListResponse: Codable {
    let outcomes: [OutcomeResponse]
    let count: Int
}

// MARK: - Outcome Feedback Request/Response

/// Request body for POST /v1/outcomes/{id}/feedback.
struct OutcomeFeedbackRequest: Codable {
    let feedback: String
    let note: String?
}

/// Response from POST /v1/outcomes/{id}/feedback (same shape as OutcomeResponse).
typealias OutcomeFeedbackResponse = OutcomeResponse

// MARK: - Outcome Stats

/// Aggregated outcome statistics from GET /v1/outcomes/stats.
struct OutcomeStatsResponse: Codable {
    let total: Int
    let positiveCount: Int
    let negativeCount: Int
    let correctionCount: Int
    let avgDurationMs: Int

    enum CodingKeys: String, CodingKey {
        case total
        case positiveCount = "positive_count"
        case negativeCount = "negative_count"
        case correctionCount = "correction_count"
        case avgDurationMs = "avg_duration_ms"
    }
}

// MARK: - Session-to-Order

/// Request body for POST /v1/orders/from-session.
struct SessionToOrderRequest: Codable {
    let sessionId: String
    let name: String?

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case name
    }
}

/// Response from POST /v1/orders/from-session.
struct SessionToOrderResponse: Codable {
    let orderId: String
    let name: String
    let status: String
    let message: String

    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case name
        case status
        case message
    }
}
