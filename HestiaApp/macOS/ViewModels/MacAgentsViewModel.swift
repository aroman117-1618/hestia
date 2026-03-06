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
    @Published var isSaving: Bool = false

    // Agent photo state
    @Published var agentPhotoData: Data?

    // Save feedback
    @Published var saveResult: SaveResult?

    enum SaveResult: Equatable {
        case success(String)
        case failure(String)
    }

    func loadAgents() async {
        isLoading = true
        defer { isLoading = false }

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

    // MARK: - Personality (ANIMA.md)

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
        isSaving = true
        defer { isSaving = false }

        do {
            _ = try await APIClient.shared.updateAgentConfigFile(
                agent.directoryName,
                fileName: "ANIMA.md",
                content: personalityContent
            )
            CacheManager.shared.invalidate(forKey: CacheKey.agentsList)
            saveResult = .success("Personality saved")
        } catch {
            saveResult = .failure("Failed to save personality")
            #if DEBUG
            print("[MacAgentsVM] Failed to save ANIMA.md for \(agent.name): \(error)")
            #endif
        }
    }

    // MARK: - Identity (IDENTITY.md)

    func saveIdentity(for agent: AgentConfigInfo, name: String, fullName: String, vibe: String, color1: String, color2: String, temperature: Double) async {
        isSaving = true
        defer { isSaving = false }

        // Reconstruct IDENTITY.md in the expected format
        let content = """
        # \(name)

        **Full Name:** \(fullName)
        **Emoji:** \(agent.identity.emoji)
        **Vibe:** \(vibe)
        **Gradient:** #\(color1) → #\(color2)
        **Invoke:** `\(agent.identity.invokePattern)`
        **Temperature:** \(String(format: "%.1f", temperature))
        """

        do {
            _ = try await APIClient.shared.updateAgentConfigFile(
                agent.directoryName,
                fileName: "IDENTITY.md",
                content: content
            )
            CacheManager.shared.invalidate(forKey: CacheKey.agentsList)
            saveResult = .success("Identity saved")
            // Reload agents to pick up the changes
            await loadAgents()
        } catch {
            saveResult = .failure("Failed to save identity")
            #if DEBUG
            print("[MacAgentsVM] Failed to save IDENTITY.md for \(agent.name): \(error)")
            #endif
        }
    }

    // MARK: - Agent Photo (V1 API, slot-based)

    /// Map agent directory name to V1 slot index
    private func slotIndex(for agent: AgentConfigInfo) -> Int? {
        switch agent.directoryName {
        case "tia": return 0
        case "mira": return 1
        case "olly": return 2
        default: return nil
        }
    }

    func loadAgentPhoto(for agent: AgentConfigInfo) async {
        guard let slot = slotIndex(for: agent) else {
            agentPhotoData = nil
            return
        }
        do {
            let data = try await APIClient.shared.getAgentPhoto(slot)
            agentPhotoData = data
        } catch {
            agentPhotoData = nil
        }
    }

    func uploadAgentPhoto(for agent: AgentConfigInfo, imageData: Data) async {
        guard let slot = slotIndex(for: agent) else { return }
        do {
            _ = try await APIClient.shared.uploadAgentPhoto(slot, imageData: imageData)
            agentPhotoData = imageData
        } catch {
            #if DEBUG
            print("[MacAgentsVM] Failed to upload photo for \(agent.name): \(error)")
            #endif
        }
    }

    func deleteAgentPhoto(for agent: AgentConfigInfo) async {
        guard let slot = slotIndex(for: agent) else { return }
        do {
            _ = try await APIClient.shared.deleteAgentPhoto(slot)
            agentPhotoData = nil
        } catch {
            #if DEBUG
            print("[MacAgentsVM] Failed to delete photo for \(agent.name): \(error)")
            #endif
        }
    }
}
