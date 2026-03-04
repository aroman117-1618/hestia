import Foundation
import HestiaShared

/// Outcome tracking and feedback API methods.
extension APIClient {
    /// Submit explicit feedback on an outcome (positive/negative/correction).
    func submitOutcomeFeedback(
        outcomeId: String,
        feedback: String,
        note: String? = nil
    ) async throws -> OutcomeFeedbackResponse {
        let encoded = outcomeId.addingPercentEncoding(
            withAllowedCharacters: .urlPathAllowed
        ) ?? outcomeId
        let body = OutcomeFeedbackRequest(feedback: feedback, note: note)
        return try await post("/outcomes/\(encoded)/feedback", body: body)
    }

    /// List outcomes with optional session filter.
    func getOutcomes(
        sessionId: String? = nil,
        limit: Int = 50
    ) async throws -> OutcomeListResponse {
        var path = "/outcomes?limit=\(limit)"
        if let sessionId {
            let encoded = sessionId.addingPercentEncoding(
                withAllowedCharacters: .urlQueryAllowed
            ) ?? sessionId
            path += "&session_id=\(encoded)"
        }
        return try await get(path)
    }

    /// Create a background order from an active chat session.
    func createOrderFromSession(
        sessionId: String,
        name: String? = nil
    ) async throws -> SessionToOrderResponse {
        let body = SessionToOrderRequest(sessionId: sessionId, name: name)
        return try await post("/orders/from-session", body: body)
    }
}
