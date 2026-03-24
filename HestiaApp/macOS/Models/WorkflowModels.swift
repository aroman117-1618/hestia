import Foundation

// MARK: - Workflow API Response Types
// No explicit CodingKeys — APIClient uses convertFromSnakeCase.
// AnyCodableValue is defined in HealthDataModels.swift (macOS target).

// MARK: - Enums

enum WorkflowStatus: String, Codable, CaseIterable, Sendable {
    case draft
    case active
    case inactive
    case archived
}

enum WorkflowTriggerType: String, Codable, CaseIterable, Sendable {
    case manual
    case schedule
}

enum WorkflowSessionStrategy: String, Codable, CaseIterable, Sendable {
    case ephemeral
    case perRun = "per_run"
    case persistent
}

enum WorkflowNodeType: String, Codable, CaseIterable, Sendable {
    case runPrompt = "run_prompt"
    case callTool = "call_tool"
    case notify
    case log
    case ifElse = "if_else"
    case switchNode = "switch"
    case schedule
    case manual
    case delay
}

enum WorkflowRunStatus: String, Codable, CaseIterable, Sendable {
    case pending
    case running
    case success
    case failed
    case cancelled
}

enum WorkflowNodeExecutionStatus: String, Codable, CaseIterable, Sendable {
    case pending
    case running
    case success
    case failed
    case skipped
}

// MARK: - List Response

struct WorkflowListResponse: Codable, Sendable {
    let workflows: [WorkflowSummary]
    let total: Int
    let limit: Int
    let offset: Int
}

struct WorkflowSummary: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let description: String
    let status: String
    let triggerType: String
    let triggerConfig: [String: AnyCodableValue]
    let sessionStrategy: String
    let version: Int
    let createdAt: String
    let updatedAt: String
    let activatedAt: String?
    let lastRunAt: String?
    let runCount: Int
    let successCount: Int
    let successRate: Double
    let migratedFromOrderId: String?

    var statusEnum: WorkflowStatus {
        WorkflowStatus(rawValue: status) ?? .draft
    }

    var triggerTypeEnum: WorkflowTriggerType {
        WorkflowTriggerType(rawValue: triggerType) ?? .manual
    }
}

// MARK: - Detail Response

struct WorkflowDetailResponse: Codable, Sendable {
    let workflow: WorkflowDetail
}

/// Full workflow with nodes and edges (from GET /{workflow_id})
/// Note: the detail endpoint returns a dict with nodes/edges embedded,
/// not nested under a "workflow" key — the dict IS the workflow.
struct WorkflowDetail: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let description: String
    let status: String
    let triggerType: String
    let triggerConfig: [String: AnyCodableValue]
    let sessionStrategy: String
    let version: Int
    let createdAt: String
    let updatedAt: String
    let activatedAt: String?
    let lastRunAt: String?
    let runCount: Int
    let successCount: Int
    let successRate: Double
    let migratedFromOrderId: String?
    let nodes: [WorkflowNodeResponse]
    let edges: [WorkflowEdgeResponse]

    var statusEnum: WorkflowStatus {
        WorkflowStatus(rawValue: status) ?? .draft
    }
}

// MARK: - Node / Edge

struct WorkflowNodeResponse: Codable, Identifiable, Sendable {
    let id: String
    let workflowId: String
    let nodeType: String
    let label: String
    let config: [String: AnyCodableValue]
    let positionX: Double
    let positionY: Double

    var nodeTypeEnum: WorkflowNodeType {
        WorkflowNodeType(rawValue: nodeType) ?? .log
    }

    /// SF Symbol for the node type
    var iconName: String {
        switch nodeTypeEnum {
        case .runPrompt: return "text.bubble"
        case .callTool: return "wrench"
        case .notify: return "bell"
        case .log: return "doc.text"
        case .ifElse: return "arrow.triangle.branch"
        case .switchNode: return "arrow.triangle.branch.fill"
        case .schedule: return "clock"
        case .manual: return "hand.tap"
        case .delay: return "timer"
        }
    }
}

struct WorkflowEdgeResponse: Codable, Identifiable, Sendable {
    let id: String
    let workflowId: String
    let sourceNodeId: String
    let targetNodeId: String
    let edgeLabel: String
}

// MARK: - Run

struct WorkflowRunListResponse: Codable, Sendable {
    let runs: [WorkflowRunResponse]
    let total: Int
    let limit: Int
    let offset: Int
}

struct WorkflowRunResponse: Codable, Identifiable, Sendable {
    let id: String
    let workflowId: String
    let workflowVersion: Int
    let status: String
    let startedAt: String
    let completedAt: String?
    let durationMs: Double?
    let triggerSource: String
    let errorMessage: String?

    var statusEnum: WorkflowRunStatus {
        WorkflowRunStatus(rawValue: status) ?? .pending
    }

    /// Human-readable duration
    var durationText: String? {
        guard let ms = durationMs else { return nil }
        if ms < 1000 { return "\(Int(ms))ms" }
        if ms < 60_000 { return String(format: "%.1fs", ms / 1000) }
        return String(format: "%.1fm", ms / 60_000)
    }
}

// MARK: - Create / Update Requests

struct WorkflowCreateRequest: Codable, Sendable {
    let name: String
    let description: String
    let triggerType: String
    let triggerConfig: [String: AnyCodableValue]
    let sessionStrategy: String
}

struct WorkflowUpdateRequest: Codable, Sendable {
    let name: String?
    let description: String?
    let triggerType: String?
    let triggerConfig: [String: AnyCodableValue]?
    let sessionStrategy: String?
}

struct NodeUpdateRequest: Codable, Sendable {
    let label: String?
    let config: [String: AnyCodableValue]?
    let nodeType: String?
    let positionX: Double?
    let positionY: Double?

    init(label: String? = nil, config: [String: AnyCodableValue]? = nil, nodeType: String? = nil, positionX: Double? = nil, positionY: Double? = nil) {
        self.label = label
        self.config = config
        self.nodeType = nodeType
        self.positionX = positionX
        self.positionY = positionY
    }
}

// MARK: - Step Builder

struct StepCreateRequest: Codable, Sendable {
    let title: String
    let prompt: String?
    let trigger: String  // "immediate" | "delay"
    let delaySeconds: Double?
    let resources: [String]?
    let positionX: Double
    let positionY: Double
    let afterNodeId: String?
}

struct StepCreateResponse: Codable, Sendable {
    let nodes: [WorkflowNodeResponse]
    let edges: [WorkflowEdgeResponse]
}

// MARK: - Tool Categories

struct ToolCategoryResponse: Codable, Sendable {
    let categories: [ToolCategory]
    let totalTools: Int
}

struct ToolCategory: Codable, Identifiable, Sendable {
    let id: String
    let label: String
    let icon: String
    let tools: [ToolSummary]
    let count: Int
}

struct ToolSummary: Codable, Identifiable, Sendable {
    let name: String
    let description: String
    let parameters: [String: AnyCodableValue]
    let requiresApproval: Bool

    var id: String { name }
}

// MARK: - Node Create

struct NodeCreateRequest: Codable, Sendable {
    let nodeType: String
    let label: String
    let config: [String: AnyCodableValue]
    let positionX: Double
    let positionY: Double
}

struct NodeCreateResponse: Codable, Sendable {
    let node: WorkflowNodeResponse
}

// MARK: - Lifecycle Responses

/// For create/update endpoints that return {"workflow": {...}} without message
struct WorkflowResponse: Codable, Sendable {
    let workflow: WorkflowSummary
}

/// For activate/deactivate endpoints that return {"workflow": {...}, "message": "..."}
struct WorkflowLifecycleResponse: Codable, Sendable {
    let workflow: WorkflowSummary
    let message: String
}

struct WorkflowTriggerResponse: Codable, Sendable {
    let run: WorkflowRunResponse
    let message: String
}

struct WorkflowDeleteResponse: Codable, Sendable {
    let workflowId: String
    let deleted: Bool
}
