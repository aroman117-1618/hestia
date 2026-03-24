import Foundation
import SwiftUI
import HestiaShared

@MainActor
class WorkflowViewModel: ObservableObject {

    // MARK: - Published State

    @Published var workflows: [WorkflowSummary] = []
    @Published var selectedWorkflowId: String?
    @Published var selectedDetail: WorkflowDetail?
    @Published var runs: [WorkflowRunResponse] = []
    @Published var isLoading = false
    @Published var isLoadingDetail = false
    @Published var errorMessage: String?
    @Published var statusFilter: WorkflowStatus?
    @Published var showingNewWorkflowSheet = false
    @Published var showCanvas = false
    @Published var selectedNodeId: String?

    // MARK: - Computed Properties

    var filteredWorkflows: [WorkflowSummary] {
        guard let filter = statusFilter else { return workflows }
        return workflows.filter { $0.statusEnum == filter }
    }

    var selectedWorkflow: WorkflowSummary? {
        guard let id = selectedWorkflowId else { return nil }
        return workflows.first { $0.id == id }
    }

    // MARK: - Dependencies

    private let client: APIClient

    init(client: APIClient = .shared) {
        self.client = client
    }

    // MARK: - Data Loading

    func loadWorkflows() async {
        errorMessage = nil
        isLoading = workflows.isEmpty
        do {
            let response = try await client.getWorkflows()
            workflows = response.workflows
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to load workflows: \(error)")
            #endif
            if workflows.isEmpty {
                errorMessage = "Could not load workflows"
            }
        }
        isLoading = false
    }

    func selectWorkflow(_ workflow: WorkflowSummary) {
        selectedWorkflowId = workflow.id
        selectedDetail = nil
        runs = []
        Task {
            await loadWorkflowDetail(workflow.id)
            await loadRuns(workflow.id)
        }
    }

    func loadWorkflowDetail(_ workflowId: String) async {
        isLoadingDetail = true
        do {
            selectedDetail = try await client.getWorkflowDetail(workflowId)
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to load detail: \(error)")
            #endif
        }
        isLoadingDetail = false
    }

    func loadRuns(_ workflowId: String) async {
        do {
            let response = try await client.getWorkflowRuns(workflowId)
            runs = response.runs
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to load runs: \(error)")
            #endif
        }
    }

    // MARK: - CRUD Actions

    func createWorkflow(name: String, description: String, triggerType: WorkflowTriggerType, sessionStrategy: WorkflowSessionStrategy) async -> Bool {
        let request = WorkflowCreateRequest(
            name: name,
            description: description,
            triggerType: triggerType.rawValue,
            triggerConfig: [:],
            sessionStrategy: sessionStrategy.rawValue
        )
        do {
            let created = try await client.createWorkflow(request)
            await loadWorkflows()
            selectWorkflow(created)
            return true
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to create: \(error)")
            #endif
            return false
        }
    }

    func deleteWorkflow(_ workflowId: String) async {
        do {
            try await client.deleteWorkflow(workflowId)
            workflows.removeAll { $0.id == workflowId }
            if selectedWorkflowId == workflowId {
                selectedWorkflowId = nil
                selectedDetail = nil
                runs = []
            }
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to delete: \(error)")
            #endif
        }
    }

    // MARK: - Lifecycle Actions

    func activateWorkflow(_ workflowId: String) async {
        do {
            _ = try await client.activateWorkflow(workflowId)
            await loadWorkflows()
            if selectedWorkflowId == workflowId {
                await loadWorkflowDetail(workflowId)
            }
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to activate: \(error)")
            #endif
        }
    }

    func deactivateWorkflow(_ workflowId: String) async {
        do {
            _ = try await client.deactivateWorkflow(workflowId)
            await loadWorkflows()
            if selectedWorkflowId == workflowId {
                await loadWorkflowDetail(workflowId)
            }
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to deactivate: \(error)")
            #endif
        }
    }

    func triggerWorkflow(_ workflowId: String) async {
        do {
            _ = try await client.triggerWorkflow(workflowId)
            // Refresh runs after trigger
            await loadRuns(workflowId)
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to trigger: \(error)")
            #endif
        }
    }

    // MARK: - Canvas Bridge Handlers

    func handleNodeSelected(_ nodeId: String) {
        selectedNodeId = nodeId
    }

    func handleNodesMoved(_ positions: [(id: String, x: Double, y: Double)]) {
        guard let workflowId = selectedWorkflowId else { return }
        Task {
            do {
                try await client.batchUpdateLayout(
                    workflowId,
                    positions: positions.map { (nodeId: $0.id, x: $0.x, y: $0.y) }
                )
            } catch {
                #if DEBUG
                print("[WorkflowVM] Failed to save layout: \(error)")
                #endif
            }
        }
    }

    func handleEdgeCreated(_ source: String, _ target: String, _ sourceHandle: String?) {
        guard let workflowId = selectedWorkflowId else { return }
        Task {
            do {
                struct EdgeReq: Codable {
                    let sourceNodeId: String
                    let targetNodeId: String
                    let edgeLabel: String
                }
                let req = EdgeReq(
                    sourceNodeId: source,
                    targetNodeId: target,
                    edgeLabel: sourceHandle ?? ""
                )
                let _: [String: AnyCodableValue] = try await client.post(
                    "/v1/workflows/\(workflowId)/edges",
                    body: req
                )
                // Refresh detail to get server-assigned edge ID
                await loadWorkflowDetail(workflowId)
            } catch {
                #if DEBUG
                print("[WorkflowVM] Failed to create edge: \(error)")
                #endif
            }
        }
    }

    func handleNodeDeleted(_ nodeId: String) {
        guard let workflowId = selectedWorkflowId else { return }
        Task {
            do {
                let _: [String: AnyCodableValue] = try await client.delete(
                    "/v1/workflows/\(workflowId)/nodes/\(nodeId)"
                )
                await loadWorkflowDetail(workflowId)
            } catch {
                #if DEBUG
                print("[WorkflowVM] Failed to delete node: \(error)")
                #endif
            }
        }
    }

    func handleEdgeDeleted(_ edgeId: String) {
        guard let workflowId = selectedWorkflowId else { return }
        Task {
            do {
                let _: [String: AnyCodableValue] = try await client.delete(
                    "/v1/workflows/\(workflowId)/edges/\(edgeId)"
                )
                await loadWorkflowDetail(workflowId)
            } catch {
                #if DEBUG
                print("[WorkflowVM] Failed to delete edge: \(error)")
                #endif
            }
        }
    }
}
