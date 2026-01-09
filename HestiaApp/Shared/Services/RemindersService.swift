import Foundation
import EventKit
import Combine

/// Protocol for reminders service operations
protocol RemindersServiceProtocol {
    /// Request reminders access permission
    func requestAccess() async -> Bool

    /// Fetch pending (incomplete) reminders
    func fetchPendingReminders(from lists: [String]?) async -> [ReminderItem]

    /// Current authorization status
    var authorizationStatus: EKAuthorizationStatus { get }
}

/// Reminders service using EventKit for real device reminders access
@MainActor
final class RemindersService: ObservableObject, RemindersServiceProtocol {
    // MARK: - Published State

    @Published private(set) var pendingReminders: [ReminderItem] = []
    @Published private(set) var isAuthorized: Bool = false
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var error: Error?

    // MARK: - Private Properties

    private let eventStore = EKEventStore()
    private var refreshTimer: Timer?

    // MARK: - Initialization

    nonisolated init() {
        // Authorization status will be updated on first access
    }

    /// Setup method to be called after init when on main actor
    func setup() {
        updateAuthorizationStatus()
    }

    deinit {
        refreshTimer?.invalidate()
    }

    // MARK: - Public Properties

    nonisolated var authorizationStatus: EKAuthorizationStatus {
        EKEventStore.authorizationStatus(for: .reminder)
    }

    // MARK: - Public Methods

    /// Request reminders access permission
    func requestAccess() async -> Bool {
        do {
            if #available(iOS 17.0, *) {
                let granted = try await eventStore.requestFullAccessToReminders()
                await MainActor.run {
                    isAuthorized = granted
                }
                return granted
            } else {
                let granted = try await eventStore.requestAccess(to: .reminder)
                await MainActor.run {
                    isAuthorized = granted
                }
                return granted
            }
        } catch {
            #if DEBUG
            print("[RemindersService] Access request failed: \(error)")
            #endif
            await MainActor.run {
                self.error = error
            }
            return false
        }
    }

    /// Fetch pending (incomplete) reminders
    /// - Parameter lists: Optional list of reminder list names to filter by. Pass nil for all lists.
    /// - Returns: Array of ReminderItem sorted by due date
    func fetchPendingReminders(from lists: [String]? = nil) async -> [ReminderItem] {
        guard isAuthorized || authorizationStatus.isGrantedForReminders else {
            return []
        }

        isLoading = true
        defer { isLoading = false }

        // Get calendars (reminder lists) to search
        let allCalendars = eventStore.calendars(for: .reminder)
        let calendarsToSearch: [EKCalendar]?

        if let listNames = lists, !listNames.isEmpty {
            calendarsToSearch = allCalendars.filter { listNames.contains($0.title) }
        } else {
            calendarsToSearch = allCalendars
        }

        guard let calendars = calendarsToSearch, !calendars.isEmpty else {
            pendingReminders = []
            return []
        }

        // Create predicate for incomplete reminders
        let predicate = eventStore.predicateForIncompleteReminders(
            withDueDateStarting: nil,
            ending: nil,
            calendars: calendars
        )

        // Fetch reminders asynchronously
        return await withCheckedContinuation { continuation in
            eventStore.fetchReminders(matching: predicate) { [weak self] reminders in
                let items = (reminders ?? []).map { reminder in
                    ReminderItem(
                        id: reminder.calendarItemIdentifier,
                        title: reminder.title ?? "Untitled",
                        dueDate: reminder.dueDateComponents?.date,
                        priority: ReminderPriority(from: reminder.priority),
                        listName: reminder.calendar?.title ?? "Unknown",
                        notes: reminder.notes,
                        isCompleted: reminder.isCompleted
                    )
                }
                .sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }

                Task { @MainActor in
                    self?.pendingReminders = items
                }
                continuation.resume(returning: items)
            }
        }
    }

    /// Start auto-refresh timer for periodic updates
    func startAutoRefresh(interval: TimeInterval = 300) {
        stopAutoRefresh()

        refreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                _ = await self?.fetchPendingReminders()
            }
        }
    }

    /// Stop auto-refresh timer
    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    // MARK: - Private Methods

    private func updateAuthorizationStatus() {
        let status = authorizationStatus
        isAuthorized = status.isGrantedForReminders
    }
}

// MARK: - Reminder Model

struct ReminderItem: Identifiable, Codable, Equatable {
    let id: String
    let title: String
    let dueDate: Date?
    let priority: ReminderPriority
    let listName: String
    let notes: String?
    let isCompleted: Bool

    var formattedDueDate: String? {
        guard let date = dueDate else { return nil }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }

    var isOverdue: Bool {
        guard let date = dueDate else { return false }
        return date < Date() && !isCompleted
    }

    var relativeDueDate: String? {
        guard let date = dueDate else { return nil }

        let calendar = Calendar.current
        let now = Date()

        if calendar.isDateInToday(date) {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return "Today at \(formatter.string(from: date))"
        } else if calendar.isDateInTomorrow(date) {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return "Tomorrow at \(formatter.string(from: date))"
        } else if date < now {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .full
            return formatter.localizedString(for: date, relativeTo: now)
        } else {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
    }
}

// MARK: - Reminder Priority

enum ReminderPriority: Int, Codable, CaseIterable {
    case none = 0
    case high = 1
    case medium = 5
    case low = 9

    init(from ekPriority: Int) {
        switch ekPriority {
        case 1...4: self = .high
        case 5: self = .medium
        case 6...9: self = .low
        default: self = .none
        }
    }

    var displayName: String {
        switch self {
        case .none: return ""
        case .high: return "High"
        case .medium: return "Medium"
        case .low: return "Low"
        }
    }

    var symbolName: String {
        switch self {
        case .none: return ""
        case .high: return "exclamationmark.3"
        case .medium: return "exclamationmark.2"
        case .low: return "exclamationmark"
        }
    }
}

// MARK: - Mock Reminders Service for Previews

final class MockRemindersService: RemindersServiceProtocol {
    var authorizationStatus: EKAuthorizationStatus = .authorized

    func requestAccess() async -> Bool {
        return true
    }

    func fetchPendingReminders(from lists: [String]?) async -> [ReminderItem] {
        return ReminderItem.mockReminders
    }
}

// MARK: - Extension for Auth Status Check

extension EKAuthorizationStatus {
    var isGrantedForReminders: Bool {
        switch self {
        case .fullAccess, .authorized:
            return true
        case .denied, .restricted, .notDetermined, .writeOnly:
            return false
        @unknown default:
            return false
        }
    }
}

// MARK: - Mock Data Extension

extension ReminderItem {
    static var mockReminders: [ReminderItem] {
        [
            ReminderItem(
                id: "mock-1",
                title: "Review project proposal",
                dueDate: Calendar.current.date(byAdding: .hour, value: 2, to: Date()),
                priority: .high,
                listName: "Work",
                notes: "Make sure to check the budget section",
                isCompleted: false
            ),
            ReminderItem(
                id: "mock-2",
                title: "Buy groceries",
                dueDate: Calendar.current.date(byAdding: .day, value: 1, to: Date()),
                priority: .medium,
                listName: "Personal",
                notes: "Milk, eggs, bread",
                isCompleted: false
            ),
            ReminderItem(
                id: "mock-3",
                title: "Call dentist",
                dueDate: nil,
                priority: .low,
                listName: "Health",
                notes: nil,
                isCompleted: false
            )
        ]
    }
}
