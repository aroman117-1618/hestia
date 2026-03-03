import Foundation
import HestiaShared

// MARK: - V2 Agent API Models

struct AgentIdentityInfo: Codable {
    let name: String
    let fullName: String
    let emoji: String
    let vibe: String
    let avatarPath: String?
    let gradientColor1: String
    let gradientColor2: String
    let invokePattern: String
    let temperature: Double
}

struct AgentConfigInfo: Codable, Identifiable {
    let directoryName: String
    let name: String
    let identity: AgentIdentityInfo
    let isDefault: Bool
    let isArchived: Bool
    let hasBootstrap: Bool
    let configVersion: String
    let createdAt: String
    let updatedAt: String
    let files: [String: Bool]

    var id: String { directoryName }
}

struct AgentConfigListInfo: Codable {
    let agents: [AgentConfigInfo]
    let count: Int
    let defaultAgent: String
}

struct AgentConfigFileInfo: Codable {
    let agentName: String
    let fileName: String
    let content: String
    let writableByAgent: Bool
    let requiresConfirmation: Bool
}

struct AgentConfigFileUpdateBody: Codable {
    let content: String
    let source: String
}

// MARK: - APIClient Extension
// Note: The base URL includes /v1, but V2 agents live at /v2/agents.
// We use "../v2/" which the server resolves correctly via URL normalization.

extension APIClient {
    func getAgentsV2() async throws -> AgentConfigListInfo {
        return try await get("../v2/agents")
    }

    func getAgentV2(_ name: String) async throws -> AgentConfigInfo {
        return try await get("../v2/agents/\(name)")
    }

    func getAgentConfigFile(_ agentName: String, fileName: String) async throws -> AgentConfigFileInfo {
        return try await get("../v2/agents/\(agentName)/config/\(fileName)")
    }

    func updateAgentConfigFile(_ agentName: String, fileName: String, content: String) async throws -> AgentConfigFileInfo {
        let body = AgentConfigFileUpdateBody(content: content, source: "user")
        return try await post("../v2/agents/\(agentName)/config/\(fileName)", body: body)
    }
}
