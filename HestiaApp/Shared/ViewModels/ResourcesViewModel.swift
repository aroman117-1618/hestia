import SwiftUI
import Combine

/// ViewModel for the Resources view (LLMs, Integrations, MCPs)
@MainActor
class ResourcesViewModel: ObservableObject {
    // MARK: - Published State

    @Published var selectedTab: Tab = .llms

    // MARK: - Tab Options

    enum Tab: String, CaseIterable, Identifiable {
        case llms = "LLMs"
        case integrations = "Integrations"
        case mcps = "MCPs"

        var id: String { rawValue }

        var iconName: String {
            switch self {
            case .llms: return "cloud"
            case .integrations: return "link"
            case .mcps: return "cpu"
            }
        }

        var description: String {
            switch self {
            case .llms: return "Cloud inference providers"
            case .integrations: return "Calendar, Reminders, Notes, Mail"
            case .mcps: return "Model Context Protocol servers"
            }
        }
    }
}
