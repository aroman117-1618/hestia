import Foundation
import HestiaShared

private struct ResearchEmptyBody: Codable {}

// MARK: - Research API Extensions

extension APIClient {
    /// Fetch the knowledge graph from the server.
    func getResearchGraph(limit: Int = 200, nodeTypes: String? = nil, centerTopic: String? = nil) async throws -> ResearchGraphResponse {
        var path = "../v1/research/graph?limit=\(limit)"
        if let types = nodeTypes {
            path += "&node_types=\(types)"
        }
        if let topic = centerTopic, !topic.isEmpty {
            path += "&center_topic=\(topic.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? topic)"
        }
        return try await get(path)
    }

    /// Trigger principle distillation from recent memory.
    func distillPrinciples(timeRangeDays: Int = 7) async throws -> DistillResponse {
        return try await post("../v1/research/principles/distill", body: ["time_range_days": timeRangeDays])
    }

    /// List principles with optional filters.
    func getPrinciples(status: String? = nil, domain: String? = nil, limit: Int = 50) async throws -> PrincipleListResponse {
        var path = "../v1/research/principles?limit=\(limit)"
        if let s = status {
            path += "&status=\(s)"
        }
        if let d = domain {
            path += "&domain=\(d)"
        }
        return try await get(path)
    }

    /// Approve a pending principle.
    func approvePrinciple(_ id: String) async throws -> PrincipleActionResponse {
        return try await post("../v1/research/principles/\(id)/approve", body: ResearchEmptyBody())
    }

    /// Reject a pending principle.
    func rejectPrinciple(_ id: String) async throws -> PrincipleActionResponse {
        return try await post("../v1/research/principles/\(id)/reject", body: ResearchEmptyBody())
    }

    /// Update a principle's content.
    func updatePrinciple(_ id: String, content: String) async throws -> PrincipleActionResponse {
        return try await put("../v1/research/principles/\(id)", body: ["content": content])
    }
}
