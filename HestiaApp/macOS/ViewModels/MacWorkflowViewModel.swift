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
    @Published var nodeStatuses: [String: String] = [:]  // nodeId → "running" | "success" | "failed"
    @Published var toolCategories: [ToolCategory] = []

    // MARK: - SSE

    private var sseTask: Task<Void, Never>?

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
                errorMessage = "Could not load orders"
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

    func createWorkflow(name: String, description: String, triggerType: WorkflowTriggerType, triggerConfig: [String: AnyCodableValue] = [:], sessionStrategy: WorkflowSessionStrategy) async -> Bool {
        let request = WorkflowCreateRequest(
            name: name,
            description: description,
            triggerType: triggerType.rawValue,
            triggerConfig: triggerConfig,
            sessionStrategy: sessionStrategy.rawValue
        )
        do {
            let created = try await client.createWorkflow(request)

            // Auto-create trigger node so canvas is never empty
            let triggerNodeType = triggerType == .schedule ? "schedule" : "manual"
            let triggerRequest = NodeCreateRequest(
                nodeType: triggerNodeType,
                label: triggerType == .schedule ? "Scheduled Trigger" : "Manual Trigger",
                config: [:],
                positionX: 250,
                positionY: 50
            )
            do {
                _ = try await client.createNode(created.id, request: triggerRequest)
            } catch {
                #if DEBUG
                print("[WorkflowVM] Auto-trigger creation failed: \(error)")
                #endif
            }

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
            // Start SSE to light up nodes in real time
            subscribeToExecutionEvents()
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to trigger: \(error)")
            #endif
        }
    }

    // MARK: - SSE Subscription

    /// Start listening for workflow execution events via SSE.
    /// Safe to call multiple times — cancels any prior subscription first.
    func subscribeToExecutionEvents() {
        sseTask?.cancel()
        sseTask = Task { [weak self] in
            guard let self else { return }
            let url = client.makeFullURL("/workflows/stream")
            var request = URLRequest(url: url)
            request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
            if let token = client.currentDeviceToken {
                request.setValue(token, forHTTPHeaderField: "X-Hestia-Device-Token")
            }

            do {
                let (bytes, _) = try await client.pinnedSession.bytes(for: request)
                var eventType = ""
                var dataBuffer = ""

                for try await line in bytes.lines {
                    if Task.isCancelled { break }

                    if line.hasPrefix("event: ") {
                        eventType = String(line.dropFirst(7))
                    } else if line.hasPrefix("data: ") {
                        dataBuffer = String(line.dropFirst(6))
                    } else if line.isEmpty && !dataBuffer.isEmpty {
                        await processSSEEvent(type: eventType, data: dataBuffer)
                        eventType = ""
                        dataBuffer = ""
                    }
                }
            } catch {
                #if DEBUG
                print("[WorkflowVM] SSE stream error: \(error)")
                #endif
            }
        }
    }

    func unsubscribeFromEvents() {
        sseTask?.cancel()
        sseTask = nil
    }

    private func processSSEEvent(type: String, data: String) async {
        guard let jsonData = data.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any]
        else { return }

        switch type {
        case "run_started":
            nodeStatuses = [:]
        case "run_completed":
            if let workflowId = selectedWorkflowId {
                await loadRuns(workflowId)
            }
        case "node_started":
            if let nodeId = json["node_id"] as? String {
                nodeStatuses[nodeId] = "running"
            }
        case "node_completed":
            if let nodeId = json["node_id"] as? String {
                nodeStatuses[nodeId] = "success"
            }
        case "node_failed":
            if let nodeId = json["node_id"] as? String {
                nodeStatuses[nodeId] = "failed"
            }
        default:
            break
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
                    "/workflows/\(workflowId)/edges",
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
                    "/workflows/\(workflowId)/nodes/\(nodeId)"
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
                    "/workflows/\(workflowId)/edges/\(edgeId)"
                )
                await loadWorkflowDetail(workflowId)
            } catch {
                #if DEBUG
                print("[WorkflowVM] Failed to delete edge: \(error)")
                #endif
            }
        }
    }

    // MARK: - Step Builder (canvas → API → inspector)

    func addStepFromCanvas(
        workflowId: String,
        stepType: String,
        title: String,
        positionX: Double,
        positionY: Double,
        afterNodeId: String?
    ) async {
        let wfId = selectedWorkflowId ?? workflowId
        do {
            var newNodeId: String?

            if stepType == "prompt" {
                // Prompt steps use the translation endpoint (handles resources, delay)
                let request = StepCreateRequest(
                    title: title,
                    prompt: "Configure this step's prompt",
                    trigger: "immediate",
                    delaySeconds: nil,
                    resources: nil,
                    positionX: positionX,
                    positionY: positionY,
                    afterNodeId: afterNodeId
                )
                let response = try await client.createNodeFromStep(wfId, step: request)
                newNodeId = response.nodes.first?.id
            } else {
                // Non-prompt types use direct node creation
                let nodeType: String
                var config: [String: AnyCodableValue] = [:]
                switch stepType {
                case "notify":
                    nodeType = "notify"
                    config["title"] = .string("Notification")
                    config["body"] = .string("")
                case "condition":
                    nodeType = "if_else"
                    config["condition"] = .dict([
                        "field": .string("response"),
                        "operator": .string("contains"),
                        "value": .string("")
                    ])
                case "tool":
                    nodeType = "call_tool"
                    config["tool_name"] = .string("read_file")  // Default; user configures in inspector
                case "delay":
                    nodeType = "delay"
                    config["delay_seconds"] = .double(60)
                default:
                    nodeType = "run_prompt"
                }

                let request = NodeCreateRequest(
                    nodeType: nodeType,
                    label: title,
                    config: config,
                    positionX: positionX,
                    positionY: positionY
                )
                let response = try await client.createNode(wfId, request: request)
                newNodeId = response.node.id

                // Create edge from afterNodeId if provided
                if let afterId = afterNodeId, let nId = newNodeId {
                    struct EdgeReq: Codable {
                        let sourceNodeId: String
                        let targetNodeId: String
                        let edgeLabel: String
                    }
                    let edgeReq = EdgeReq(sourceNodeId: afterId, targetNodeId: nId, edgeLabel: "")
                    let _: [String: AnyCodableValue] = try await client.post(
                        "/workflows/\(wfId)/edges",
                        body: edgeReq
                    )
                }
            }

            // Reload workflow to sync canvas
            await loadWorkflowDetail(wfId)

            // Auto-select the new node to open inspector
            if let nodeId = newNodeId {
                selectedNodeId = nodeId
            }
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to add step: \(error)")
            #endif
            errorMessage = "Failed to add step"
        }
    }

    func fetchToolCategories() async {
        guard toolCategories.isEmpty else { return }
        do {
            let response = try await client.getToolCategories()
            toolCategories = response.categories
        } catch {
            #if DEBUG
            print("[WorkflowVM] Failed to fetch tool categories: \(error)")
            #endif
        }
    }
}
