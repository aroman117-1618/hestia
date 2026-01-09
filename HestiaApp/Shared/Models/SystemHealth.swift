import SwiftUI

/// System health status from the backend
struct SystemHealth: Codable {
    let status: HealthStatus
    let timestamp: Date
    let components: HealthComponents
}

/// Overall health status
enum HealthStatus: String, Codable {
    case healthy
    case degraded
    case unhealthy

    /// Color for status indicator
    var color: Color {
        switch self {
        case .healthy: return .healthyGreen
        case .degraded: return .warningYellow
        case .unhealthy: return .errorRed
        }
    }

    /// SF Symbol for status
    var iconName: String {
        switch self {
        case .healthy: return "checkmark.circle.fill"
        case .degraded: return "exclamationmark.triangle.fill"
        case .unhealthy: return "xmark.circle.fill"
        }
    }

    /// Human-readable description
    var displayText: String {
        switch self {
        case .healthy: return "All Systems Operational"
        case .degraded: return "Some Systems Degraded"
        case .unhealthy: return "System Issues Detected"
        }
    }
}

/// Health status of all system components
struct HealthComponents: Codable {
    let inference: InferenceHealth
    let memory: MemoryHealth
    let stateMachine: StateMachineHealth
    let tools: ToolsHealth

    enum CodingKeys: String, CodingKey {
        case inference
        case memory
        case stateMachine = "state_machine"
        case tools
    }
}

/// Inference layer health
struct InferenceHealth: Codable {
    let status: HealthStatus
    let ollamaAvailable: Bool
    let primaryModelAvailable: Bool
    let complexModelAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case status
        case ollamaAvailable = "ollama_available"
        case primaryModelAvailable = "primary_model_available"
        case complexModelAvailable = "complex_model_available"
    }
}

/// Memory layer health
struct MemoryHealth: Codable {
    let status: HealthStatus
    let vectorCount: Int

    enum CodingKeys: String, CodingKey {
        case status
        case vectorCount = "vector_count"
    }
}

/// State machine health
struct StateMachineHealth: Codable {
    let status: HealthStatus
    let activeTasks: Int

    enum CodingKeys: String, CodingKey {
        case status
        case activeTasks = "active_tasks"
    }
}

/// Tools health
struct ToolsHealth: Codable {
    let status: HealthStatus
    let registeredTools: Int
    let toolNames: [String]

    enum CodingKeys: String, CodingKey {
        case status
        case registeredTools = "registered_tools"
        case toolNames = "tool_names"
    }
}

// MARK: - Mock Data

extension SystemHealth {
    static let mockHealthy = SystemHealth(
        status: .healthy,
        timestamp: Date(),
        components: HealthComponents(
            inference: InferenceHealth(
                status: .healthy,
                ollamaAvailable: true,
                primaryModelAvailable: true,
                complexModelAvailable: true
            ),
            memory: MemoryHealth(
                status: .healthy,
                vectorCount: 1234
            ),
            stateMachine: StateMachineHealth(
                status: .healthy,
                activeTasks: 0
            ),
            tools: ToolsHealth(
                status: .healthy,
                registeredTools: 23,
                toolNames: ["list_calendars", "create_event", "list_reminders"]
            )
        )
    )

    static let mockDegraded = SystemHealth(
        status: .degraded,
        timestamp: Date(),
        components: HealthComponents(
            inference: InferenceHealth(
                status: .degraded,
                ollamaAvailable: true,
                primaryModelAvailable: true,
                complexModelAvailable: false
            ),
            memory: MemoryHealth(
                status: .healthy,
                vectorCount: 1234
            ),
            stateMachine: StateMachineHealth(
                status: .healthy,
                activeTasks: 1
            ),
            tools: ToolsHealth(
                status: .healthy,
                registeredTools: 23,
                toolNames: ["list_calendars", "create_event"]
            )
        )
    )
}
