import Foundation
import HestiaShared

/// Proactive intelligence API methods.
extension APIClient {
    func getProactivePolicy() async throws -> ProactivePolicyResponse {
        return try await get("/v1/proactive/policy")
    }

    func updateProactivePolicy(_ request: ProactivePolicyUpdateRequest) async throws -> ProactivePolicyResponse {
        return try await post("/v1/proactive/policy", body: request)
    }

    func getProactivePatterns() async throws -> ProactivePatternResponse {
        return try await get("/v1/proactive/patterns")
    }
}
