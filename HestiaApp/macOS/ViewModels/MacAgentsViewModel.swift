import SwiftUI
import HestiaShared

@MainActor
class MacAgentsViewModel: ObservableObject {
    @Published var agents: [AgentConfigInfo] = []
    @Published var defaultAgent: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // Detail sheet state
    @Published var selectedAgent: AgentConfigInfo?
    @Published var personalityContent: String = ""
    @Published var isLoadingPersonality: Bool = false

    func loadAgents() async {
        isLoading = true
        defer { isLoading = false }

        // Try cache first
        if let cached = CacheManager.shared.get(AgentConfigListInfo.self, forKey: CacheKey.agentsList) {
            agents = cached.agents
            defaultAgent = cached.defaultAgent
        }

        do {
            let response = try await APIClient.shared.getAgentsV2()
            agents = response.agents.filter { !$0.isArchived }
            defaultAgent = response.defaultAgent
            errorMessage = nil
            CacheManager.shared.cache(response, forKey: CacheKey.agentsList)
        } catch {
            #if DEBUG
            print("[MacAgentsVM] Failed to load agents: \(error)")
            #endif
            if agents.isEmpty {
                errorMessage = "Failed to load agents: \(error.localizedDescription)"
            }
        }
    }

    func loadPersonality(for agent: AgentConfigInfo) async {
        isLoadingPersonality = true
        defer { isLoadingPersonality = false }

        do {
            let file = try await APIClient.shared.getAgentConfigFile(agent.directoryName, fileName: "ANIMA.md")
            personalityContent = file.content
        } catch {
            personalityContent = ""
            #if DEBUG
            print("[MacAgentsVM] Failed to load ANIMA.md for \(agent.name): \(error)")
            #endif
        }
    }

    func savePersonality(for agent: AgentConfigInfo) async {
        do {
            _ = try await APIClient.shared.updateAgentConfigFile(
                agent.directoryName,
                fileName: "ANIMA.md",
                content: personalityContent
            )
            CacheManager.shared.invalidate(forKey: CacheKey.agentsList)
        } catch {
            #if DEBUG
            print("[MacAgentsVM] Failed to save ANIMA.md for \(agent.name): \(error)")
            #endif
            errorMessage = "Failed to save personality"
        }
    }
}
