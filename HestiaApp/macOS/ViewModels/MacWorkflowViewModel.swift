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
}
