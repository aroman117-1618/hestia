import Foundation
import HestiaShared

/// Workflow API methods for macOS workflow manager.
extension APIClient {

    // MARK: - Workflow CRUD

    func getWorkflows(status: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> WorkflowListResponse {
        var path = "/v1/workflows?limit=\(limit)&offset=\(offset)"
        if let status { path += "&status=\(status)" }
        return try await get(path)
    }

    func getWorkflowDetail(_ workflowId: String) async throws -> WorkflowDetail {
        let response: WorkflowDetailResponse = try await get("/v1/workflows/\(workflowId)")
        return response.workflow
    }

    func createWorkflow(_ request: WorkflowCreateRequest) async throws -> WorkflowSummary {
        let response: WorkflowLifecycleResponse = try await post("/v1/workflows", body: request)
        return response.workflow
    }

    func updateWorkflow(_ workflowId: String, _ request: WorkflowUpdateRequest) async throws -> WorkflowSummary {
        let response: WorkflowLifecycleResponse = try await patch("/v1/workflows/\(workflowId)", body: request)
        return response.workflow
    }

    func deleteWorkflow(_ workflowId: String) async throws {
        let _: WorkflowDeleteResponse = try await delete("/v1/workflows/\(workflowId)")
    }

    // MARK: - Lifecycle

    func activateWorkflow(_ workflowId: String) async throws -> WorkflowLifecycleResponse {
        struct Empty: Codable {}
        return try await post("/v1/workflows/\(workflowId)/activate", body: Empty())
    }

    func deactivateWorkflow(_ workflowId: String) async throws -> WorkflowLifecycleResponse {
        struct Empty: Codable {}
        return try await post("/v1/workflows/\(workflowId)/deactivate", body: Empty())
    }

    // MARK: - Execution

    func triggerWorkflow(_ workflowId: String) async throws -> WorkflowTriggerResponse {
        struct Empty: Codable {}
        return try await post("/v1/workflows/\(workflowId)/trigger", body: Empty())
    }

    func getWorkflowRuns(_ workflowId: String, limit: Int = 20, offset: Int = 0) async throws -> WorkflowRunListResponse {
        return try await get("/v1/workflows/\(workflowId)/runs?limit=\(limit)&offset=\(offset)")
    }

    // MARK: - Layout

    func batchUpdateLayout(_ workflowId: String, positions: [(nodeId: String, x: Double, y: Double)]) async throws {
        struct Position: Codable {
            let nodeId: String
            let positionX: Double
            let positionY: Double
        }
        struct LayoutRequest: Codable {
            let positions: [Position]
        }
        struct LayoutResponse: Codable {
            let updated: Int
            let workflowId: String
        }
        let req = LayoutRequest(positions: positions.map {
            Position(nodeId: $0.nodeId, positionX: $0.x, positionY: $0.y)
        })
        let _: LayoutResponse = try await patch("/v1/workflows/\(workflowId)/layout", body: req)
    }
}
