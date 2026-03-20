import SwiftUI
import HestiaShared
import EventKit
import Combine

// MARK: - Integration Models (macOS)

enum IntegrationType: String, CaseIterable, Identifiable {
    case calendar
    case reminders
    case notes
    case mail

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .calendar: return "Calendar"
        case .reminders: return "Reminders"
        case .notes: return "Notes"
        case .mail: return "Mail"
        }
    }

    var iconName: String {
        switch self {
        case .calendar: return "calendar"
        case .reminders: return "checklist"
        case .notes: return "note.text"
        case .mail: return "envelope"
        }
    }

    var requiresDevicePermission: Bool {
        switch self {
        case .calendar, .reminders: return true
        case .notes, .mail: return false
        }
    }
}

enum IntegrationStatus: Equatable {
    case connected
    case notConnected
    case denied
    case backendOnly

    var displayName: String {
        switch self {
        case .connected: return "Connected"
        case .notConnected: return "Not Connected"
        case .denied: return "Denied"
        case .backendOnly: return "Backend"
        }
    }

    var color: Color {
        switch self {
        case .connected: return MacColors.healthGreen
        case .notConnected: return MacColors.textFaint
        case .denied: return MacColors.healthRed
        case .backendOnly: return MacColors.statusInfo
        }
    }
}

struct IntegrationTool: Identifiable {
    let id: String
    let name: String
    let description: String
    let requiresApproval: Bool
}

struct Integration: Identifiable {
    let id: IntegrationType
    var status: IntegrationStatus
    let tools: [IntegrationTool]

    var name: String { id.displayName }
    var iconName: String { id.iconName }
    var toolCount: Int { tools.count }
    var requiresDevicePermission: Bool { id.requiresDevicePermission }
}

// MARK: - ViewModel

@MainActor
class MacIntegrationsViewModel: ObservableObject {
    @Published var integrations: [Integration] = []
    @Published var isLoading: Bool = false

    private let eventStore = EKEventStore()
    private var apiTools: [ToolDefinitionAPI] = []

    nonisolated init() {}

    func setup() {
        buildIntegrations()
        Task { [weak self] in
            await self?.loadTools()
        }
    }

    private func loadTools() async {
        let (response, _) = await CacheFetcher.load(
            key: CacheKey.integrationsStatus,
            ttl: CacheTTL.stable
        ) {
            try await APIClient.shared.getTools()
        }

        if let response {
            apiTools = response.tools
            buildIntegrations()
            #if DEBUG
            print("[MacIntegrationsVM] Loaded \(response.count) tools from API")
            #endif
        }
    }

    func refresh() {
        buildIntegrations()
    }

    func requestPermission(for type: IntegrationType) async {
        switch type {
        case .calendar:
            do {
                try await eventStore.requestFullAccessToEvents()
            } catch {
                #if DEBUG
                print("[MacIntegrationsVM] Calendar permission error: \(error)")
                #endif
            }

        case .reminders:
            do {
                try await eventStore.requestFullAccessToReminders()
            } catch {
                #if DEBUG
                print("[MacIntegrationsVM] Reminders permission error: \(error)")
                #endif
            }

        case .notes, .mail:
            break
        }

        refresh()
    }

    // MARK: - Private

    private func buildIntegrations() {
        integrations = IntegrationType.allCases.map { type in
            Integration(
                id: type,
                status: statusFor(type),
                tools: toolsFor(type)
            )
        }
    }

    private func statusFor(_ type: IntegrationType) -> IntegrationStatus {
        switch type {
        case .calendar:
            return mapEventKitStatus(EKEventStore.authorizationStatus(for: .event))
        case .reminders:
            return mapEventKitStatus(EKEventStore.authorizationStatus(for: .reminder))
        case .notes, .mail:
            return .backendOnly
        }
    }

    private func mapEventKitStatus(_ status: EKAuthorizationStatus) -> IntegrationStatus {
        switch status {
        case .fullAccess, .authorized:
            return .connected
        case .denied, .restricted:
            return .denied
        case .notDetermined, .writeOnly:
            return .notConnected
        @unknown default:
            return .notConnected
        }
    }

    private static let categoryMap: [String: IntegrationType] = [
        "calendar": .calendar,
        "reminders": .reminders,
        "notes": .notes,
        "mail": .mail,
    ]

    private func toolsFor(_ type: IntegrationType) -> [IntegrationTool] {
        let apiMatches = apiTools.filter { tool in
            Self.categoryMap[tool.category] == type
        }
        if !apiMatches.isEmpty {
            return apiMatches.map { tool in
                IntegrationTool(
                    id: tool.name,
                    name: tool.name.replacingOccurrences(of: "_", with: " ").capitalized,
                    description: tool.description,
                    requiresApproval: tool.requiresApproval
                )
            }
        }
        return fallbackToolsFor(type)
    }

    private func fallbackToolsFor(_ type: IntegrationType) -> [IntegrationTool] {
        switch type {
        case .calendar:
            return [
                IntegrationTool(id: "list_calendars", name: "List Calendars", description: "List all available calendars", requiresApproval: false),
                IntegrationTool(id: "list_events", name: "List Events", description: "List upcoming calendar events", requiresApproval: false),
                IntegrationTool(id: "create_event", name: "Create Event", description: "Create a new calendar event", requiresApproval: true),
                IntegrationTool(id: "delete_event", name: "Delete Event", description: "Delete a calendar event", requiresApproval: true),
            ]
        case .reminders:
            return [
                IntegrationTool(id: "list_reminder_lists", name: "List Reminder Lists", description: "List all reminder lists", requiresApproval: false),
                IntegrationTool(id: "list_reminders", name: "List Reminders", description: "List reminders from a list", requiresApproval: false),
                IntegrationTool(id: "create_reminder", name: "Create Reminder", description: "Create a new reminder", requiresApproval: true),
                IntegrationTool(id: "complete_reminder", name: "Complete Reminder", description: "Mark a reminder as complete", requiresApproval: true),
            ]
        case .notes:
            return [
                IntegrationTool(id: "list_note_folders", name: "List Folders", description: "List all note folders", requiresApproval: false),
                IntegrationTool(id: "list_notes", name: "List Notes", description: "List notes in a folder", requiresApproval: false),
                IntegrationTool(id: "get_note", name: "Get Note", description: "Read a specific note", requiresApproval: false),
                IntegrationTool(id: "create_note", name: "Create Note", description: "Create a new note", requiresApproval: true),
            ]
        case .mail:
            return [
                IntegrationTool(id: "list_mailboxes", name: "List Mailboxes", description: "List all mail folders", requiresApproval: false),
                IntegrationTool(id: "list_messages", name: "List Messages", description: "List messages in a mailbox", requiresApproval: false),
                IntegrationTool(id: "get_message", name: "Get Message", description: "Read a specific email", requiresApproval: false),
                IntegrationTool(id: "search_messages", name: "Search Messages", description: "Search emails by keyword", requiresApproval: false),
            ]
        }
    }
}
