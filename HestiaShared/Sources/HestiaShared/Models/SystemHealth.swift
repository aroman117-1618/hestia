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
/// Note: No explicit CodingKeys — APIClient decoder uses convertFromSnakeCase globally.
/// Explicit CodingKeys with snake_case raw values conflict with convertFromSnakeCase
/// (double conversion: JSON key converted THEN CodingKey raw value can't match).
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

    // Custom decoder: server may return null for booleans before Ollama status is checked
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        status = try container.decode(HealthStatus.self, forKey: .status)
        ollamaAvailable = (try? container.decode(Bool.self, forKey: .ollamaAvailable)) ?? false
        primaryModelAvailable = (try? container.decode(Bool.self, forKey: .primaryModelAvailable)) ?? false
        complexModelAvailable = (try? container.decode(Bool.self, forKey: .complexModelAvailable)) ?? false
    }

    // CodingKeys needed for custom init(from:) — use camelCase (convertFromSnakeCase handles the rest)
    enum CodingKeys: String, CodingKey {
        case status
        case ollamaAvailable
        case primaryModelAvailable
        case complexModelAvailable
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
}

/// State machine health
public struct StateMachineHealth: Codable, Sendable {
    public let status: HealthStatus
    public let activeTasks: Int

    public init(status: HealthStatus, activeTasks: Int) {
        self.status = status
        self.activeTasks = activeTasks
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
