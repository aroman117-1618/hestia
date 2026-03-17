import SwiftUI

/// System health status from the backend
public struct SystemHealth: Codable, Sendable {
    public let status: HealthStatus
    public let timestamp: Date
    public let components: HealthComponents

    public init(status: HealthStatus, timestamp: Date, components: HealthComponents) {
        self.status = status
        self.timestamp = timestamp
        self.components = components
    }
}

/// Overall health status
public enum HealthStatus: String, Codable, Sendable {
    case healthy
    case degraded
    case unhealthy

    /// Color for status indicator
    public var color: Color {
        switch self {
        case .healthy: return .healthyGreen
        case .degraded: return .warningYellow
        case .unhealthy: return .errorRed
        }
    }

    /// SF Symbol for status
    public var iconName: String {
        switch self {
        case .healthy: return "checkmark.circle.fill"
        case .degraded: return "exclamationmark.triangle.fill"
        case .unhealthy: return "xmark.circle.fill"
        }
    }

    /// Human-readable description
    public var displayText: String {
        switch self {
        case .healthy: return "All Systems Operational"
        case .degraded: return "Some Systems Degraded"
        case .unhealthy: return "System Issues Detected"
        }
    }
}

/// Health status of all system components
public struct HealthComponents: Codable, Sendable {
    public let inference: InferenceHealth
    public let memory: MemoryHealth
    public let stateMachine: StateMachineHealth
    public let tools: ToolsHealth

    public init(inference: InferenceHealth, memory: MemoryHealth, stateMachine: StateMachineHealth, tools: ToolsHealth) {
        self.inference = inference
        self.memory = memory
        self.stateMachine = stateMachine
        self.tools = tools
    }

    enum CodingKeys: String, CodingKey {
        case inference
        case memory
        case stateMachine = "state_machine"
        case tools
    }
}

/// Inference layer health
public struct InferenceHealth: Codable, Sendable {
    public let status: HealthStatus
    public let ollamaAvailable: Bool
    public let primaryModelAvailable: Bool
    public let complexModelAvailable: Bool

    public init(status: HealthStatus, ollamaAvailable: Bool, primaryModelAvailable: Bool, complexModelAvailable: Bool) {
        self.status = status
        self.ollamaAvailable = ollamaAvailable
        self.primaryModelAvailable = primaryModelAvailable
        self.complexModelAvailable = complexModelAvailable
    }

    enum CodingKeys: String, CodingKey {
        case status
        case ollamaAvailable = "ollama_available"
        case primaryModelAvailable = "primary_model_available"
        case complexModelAvailable = "complex_model_available"
    }
}

/// Memory layer health
public struct MemoryHealth: Codable, Sendable {
    public let status: HealthStatus
    public let vectorCount: Int

    public init(status: HealthStatus, vectorCount: Int) {
        self.status = status
        self.vectorCount = vectorCount
    }

    enum CodingKeys: String, CodingKey {
        case status
        case vectorCount = "vector_count"
    }
}

/// State machine health
public struct StateMachineHealth: Codable, Sendable {
    public let status: HealthStatus
    public let activeTasks: Int

    public init(status: HealthStatus, activeTasks: Int) {
        self.status = status
        self.activeTasks = activeTasks
    }

    enum CodingKeys: String, CodingKey {
        case status
        case activeTasks = "active_tasks"
    }
}

/// Tools health
public struct ToolsHealth: Codable, Sendable {
    public let status: HealthStatus
    public let registeredTools: Int
    public let toolNames: [String]

    public init(status: HealthStatus, registeredTools: Int, toolNames: [String]) {
        self.status = status
        self.registeredTools = registeredTools
        self.toolNames = toolNames
    }

    enum CodingKeys: String, CodingKey {
        case status
        case registeredTools = "registered_tools"
        case toolNames = "tool_names"
    }
}

// MARK: - Mock Data

extension SystemHealth {
    public static let mockHealthy = SystemHealth(
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

    public static let mockDegraded = SystemHealth(
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
