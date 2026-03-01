import SwiftUI
import HestiaShared
import UIKit
import EventKit
import HealthKit
import Combine

// MARK: - Integration Models

/// Type of Apple integration
enum IntegrationType: String, CaseIterable, Identifiable {
    case calendar
    case reminders
    case notes
    case mail
    case health

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .calendar: return "Calendar"
        case .reminders: return "Reminders"
        case .notes: return "Notes"
        case .mail: return "Mail"
        case .health: return "Health"
        }
    }

    var iconName: String {
        switch self {
        case .calendar: return "calendar"
        case .reminders: return "checklist"
        case .notes: return "note.text"
        case .mail: return "envelope"
        case .health: return "heart.fill"
        }
    }

    /// Whether this integration requires iOS device permissions
    var requiresDevicePermission: Bool {
        switch self {
        case .calendar, .reminders, .health: return true
        case .notes, .mail: return false
        }
    }
}

/// Permission/connection status for an integration
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
        case .connected: return .healthyGreen
        case .notConnected: return .white.opacity(0.5)
        case .denied: return .errorRed
        case .backendOnly: return .blue
        }
    }
}

/// A tool provided by an integration
struct IntegrationTool: Identifiable {
    let id: String
    let name: String
    let description: String
    let requiresApproval: Bool
}

/// An Apple integration with its current status
struct Integration: Identifiable {
    let id: IntegrationType
    var status: IntegrationStatus
    let tools: [IntegrationTool]

    var name: String { id.displayName }
    var iconName: String { id.iconName }
    var toolCount: Int { tools.count }
    var requiresDevicePermission: Bool { id.requiresDevicePermission }
}

// MARK: - UserDefaults Keys

/// Constants for integration-related UserDefaults keys
enum IntegrationKeys {
    static let calendarExcluded = "hestia.calendar.excludedCalendars"
    static let calendarExcludeAllDay = "hestia.calendar.excludeAllDay"
    static let calendarLookAheadDays = "hestia.calendar.lookAheadDays"
    static let healthSyncEnabled = "hestia.health.syncEnabled"
    static let healthLastSync = "hestia.health.lastSyncDate"
}

// MARK: - ViewModel

/// Manages integration state, permissions, and configuration
@MainActor
class IntegrationsViewModel: ObservableObject {
    // MARK: - Published State

    @Published var integrations: [Integration] = []
    @Published var isLoading: Bool = false

    // MARK: - Private

    private let eventStore = EKEventStore()
    private var foregroundObserver: AnyCancellable?
    private var apiTools: [ToolDefinitionAPI] = []

    // MARK: - Calendar Config (UserDefaults-backed)

    @Published var calendarExcludedNames: [String] = [] {
        didSet {
            UserDefaults.standard.set(calendarExcludedNames, forKey: IntegrationKeys.calendarExcluded)
        }
    }

    @Published var calendarExcludeAllDay: Bool = true {
        didSet {
            UserDefaults.standard.set(calendarExcludeAllDay, forKey: IntegrationKeys.calendarExcludeAllDay)
        }
    }

    @Published var calendarLookAheadDays: Int = 7 {
        didSet {
            UserDefaults.standard.set(calendarLookAheadDays, forKey: IntegrationKeys.calendarLookAheadDays)
        }
    }

    // MARK: - Initialization

    nonisolated init() {
        // Default values set on property declarations
        // UserDefaults values loaded in setup() on main actor
    }

    /// Setup method — call from .onAppear to start observing foreground events
    func setup() {
        // Load calendar config from UserDefaults
        let defaults = UserDefaults.standard
        calendarExcludedNames = defaults.stringArray(forKey: IntegrationKeys.calendarExcluded) ?? ["aLonati"]
        calendarExcludeAllDay = defaults.object(forKey: IntegrationKeys.calendarExcludeAllDay) as? Bool ?? true
        calendarLookAheadDays = defaults.object(forKey: IntegrationKeys.calendarLookAheadDays) as? Int ?? 7

        // Build initial integration list (hardcoded fallback while API loads)
        buildIntegrations()

        // Load tools from API in background
        Task { [weak self] in
            await self?.loadTools()
        }

        // Observe app returning to foreground to refresh permission states
        foregroundObserver = NotificationCenter.default
            .publisher(for: UIApplication.willEnterForegroundNotification)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.refresh()
            }
    }

    /// Fetch tool definitions from the backend API
    private func loadTools() async {
        do {
            let response = try await APIClient.shared.getTools()
            apiTools = response.tools
            buildIntegrations()
            #if DEBUG
            print("[IntegrationsViewModel] Loaded \(response.count) tools from API")
            #endif
        } catch {
            #if DEBUG
            print("[IntegrationsViewModel] Failed to load tools from API, using fallback: \(error)")
            #endif
        }
    }

    // MARK: - Public Methods

    /// Refresh all integration statuses
    func refresh() {
        buildIntegrations()
    }

    /// Request permission for an integration that requires device access
    func requestPermission(for type: IntegrationType) async {
        switch type {
        case .calendar:
            let calendarService = CalendarService()
            calendarService.setup()
            _ = await calendarService.requestAccess()

        case .reminders:
            let remindersService = RemindersService()
            remindersService.setup()
            _ = await remindersService.requestAccess()

        case .health:
            let healthService = HealthKitService()
            healthService.setup()
            _ = await healthService.requestAuthorization()

        case .notes, .mail:
            break // No device permissions needed
        }

        // Refresh status after permission request
        refresh()
    }

    /// Get a specific integration by type
    func integration(for type: IntegrationType) -> Integration? {
        integrations.first { $0.id == type }
    }

    /// Get available device calendars for the exclusion picker
    func availableCalendarNames() -> [String] {
        let calendars = eventStore.calendars(for: .event)
        return calendars.map { $0.title }.sorted()
    }

    // MARK: - Private Methods

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
            let status = EKEventStore.authorizationStatus(for: .event)
            return mapEventKitStatus(status)

        case .reminders:
            let status = EKEventStore.authorizationStatus(for: .reminder)
            return mapEventKitStatus(status)

        case .health:
            return mapHealthKitStatus()

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

    private func mapHealthKitStatus() -> IntegrationStatus {
        guard HKHealthStore.isHealthDataAvailable() else {
            return .denied
        }

        // HealthKit doesn't expose per-type read authorization.
        // Use a representative type (step count) to check general status.
        let store = HKHealthStore()
        let stepType = HKQuantityType(.stepCount)
        let status = store.authorizationStatus(for: stepType)

        switch status {
        case .sharingAuthorized:
            return .connected
        case .sharingDenied:
            return .denied
        case .notDetermined:
            return .notConnected
        @unknown default:
            return .notConnected
        }
    }

    // MARK: - Tool Definitions (API-first with hardcoded fallback)

    /// Map backend tool categories to IntegrationType
    private static let categoryMap: [String: IntegrationType] = [
        "calendar": .calendar,
        "reminders": .reminders,
        "notes": .notes,
        "mail": .mail,
        "health": .health,
    ]

    private func toolsFor(_ type: IntegrationType) -> [IntegrationTool] {
        // Prefer API-fetched tools if available
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

        // Hardcoded fallback when API is unreachable
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
                IntegrationTool(id: "delete_reminder", name: "Delete Reminder", description: "Delete a reminder", requiresApproval: true),
                IntegrationTool(id: "update_reminder", name: "Update Reminder", description: "Update a reminder's details", requiresApproval: true),
            ]

        case .notes:
            return [
                IntegrationTool(id: "list_note_folders", name: "List Folders", description: "List all note folders", requiresApproval: false),
                IntegrationTool(id: "list_notes", name: "List Notes", description: "List notes in a folder", requiresApproval: false),
                IntegrationTool(id: "get_note", name: "Get Note", description: "Read a specific note", requiresApproval: false),
                IntegrationTool(id: "create_note", name: "Create Note", description: "Create a new note", requiresApproval: true),
                IntegrationTool(id: "update_note", name: "Update Note", description: "Update an existing note", requiresApproval: true),
            ]

        case .mail:
            return [
                IntegrationTool(id: "list_mailboxes", name: "List Mailboxes", description: "List all mail folders", requiresApproval: false),
                IntegrationTool(id: "list_messages", name: "List Messages", description: "List messages in a mailbox", requiresApproval: false),
                IntegrationTool(id: "get_message", name: "Get Message", description: "Read a specific email", requiresApproval: false),
                IntegrationTool(id: "search_messages", name: "Search Messages", description: "Search emails by keyword", requiresApproval: false),
                IntegrationTool(id: "get_unread_count", name: "Unread Count", description: "Get unread message count", requiresApproval: false),
            ]

        case .health:
            return [
                IntegrationTool(id: "get_health_summary", name: "Health Summary", description: "Today's health metrics overview", requiresApproval: false),
                IntegrationTool(id: "get_health_trend", name: "Health Trend", description: "Metric trends over time", requiresApproval: false),
                IntegrationTool(id: "get_sleep_analysis", name: "Sleep Analysis", description: "Sleep duration and consistency", requiresApproval: false),
                IntegrationTool(id: "get_activity_report", name: "Activity Report", description: "Steps, distance, and calories", requiresApproval: false),
                IntegrationTool(id: "get_vitals", name: "Vitals", description: "Latest vital sign readings", requiresApproval: false),
            ]
        }
    }
}
