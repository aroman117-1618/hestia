import Foundation
import HestiaShared

/// Workflow API methods for macOS workflow manager.
extension APIClient {

    // MARK: - Workflow CRUD

    func getWorkflows(status: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> WorkflowListResponse {
        var path = "/workflows?limit=\(limit)&offset=\(offset)"
        if let status { path += "&status=\(status)" }
        return try await get(path)
    }

    func getWorkflowDetail(_ workflowId: String) async throws -> WorkflowDetail {
        let response: WorkflowDetailResponse = try await get("/workflows/\(workflowId)")
        return response.workflow
    }

    func createWorkflow(_ request: WorkflowCreateRequest) async throws -> WorkflowSummary {
        let response: WorkflowResponse = try await post("/workflows", body: request)
        return response.workflow
    }

    func updateWorkflow(_ workflowId: String, _ request: WorkflowUpdateRequest) async throws -> WorkflowSummary {
        let response: WorkflowResponse = try await patch("/workflows/\(workflowId)", body: request)
        return response.workflow
    }

    func deleteWorkflow(_ workflowId: String) async throws {
        let _: WorkflowDeleteResponse = try await delete("/workflows/\(workflowId)")
    }

    // MARK: - Lifecycle

    func activateWorkflow(_ workflowId: String) async throws -> WorkflowLifecycleResponse {
        struct Empty: Codable {}
        return try await post("/workflows/\(workflowId)/activate", body: Empty())
    }

    func deactivateWorkflow(_ workflowId: String) async throws -> WorkflowLifecycleResponse {
        struct Empty: Codable {}
        return try await post("/workflows/\(workflowId)/deactivate", body: Empty())
    }

    // MARK: - Execution

    func triggerWorkflow(_ workflowId: String) async throws -> WorkflowTriggerResponse {
        struct Empty: Codable {}
        return try await post("/workflows/\(workflowId)/trigger", body: Empty())
    }

    func getWorkflowRuns(_ workflowId: String, limit: Int = 20, offset: Int = 0) async throws -> WorkflowRunListResponse {
        return try await get("/workflows/\(workflowId)/runs?limit=\(limit)&offset=\(offset)")
    }

    func getRunDetail(_ workflowId: String, runId: String) async throws -> WorkflowRunDetail {
        let response: WorkflowRunDetailResponse = try await get("/workflows/\(workflowId)/runs/\(runId)")
        return response.run
    }

    // MARK: - Node Update

    func patchNode(_ workflowId: String, nodeId: String, request: NodeUpdateRequest) async throws {
        let _: [String: AnyCodableValue] = try await patch(
            "/workflows/\(workflowId)/nodes/\(nodeId)",
            body: request
        )
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
        let _: LayoutResponse = try await patch("/workflows/\(workflowId)/layout", body: req)
    }

    // MARK: - Step Builder

    func createNodeFromStep(_ workflowId: String, step: StepCreateRequest) async throws -> StepCreateResponse {
        return try await post("/workflows/\(workflowId)/nodes/from-step", body: step)
    }

    func createNode(_ workflowId: String, request: NodeCreateRequest) async throws -> NodeCreateResponse {
        return try await post("/workflows/\(workflowId)/nodes", body: request)
    }

    func getToolCategories() async throws -> ToolCategoryResponse {
        return try await get("/tools/categories")
    }
}
