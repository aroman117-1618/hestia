import SwiftUI
import EventKit

/// ViewModel for the Internal sub-tab of Command.
/// Loads today's calendar events and reminders via EventKit.
@MainActor
class InternalTabViewModel: ObservableObject {

    // MARK: - Published State

    @Published var todayEvents: [EKEvent] = []
    @Published var todayReminders: [EKReminder] = []
    @Published var isLoading = false

    // MARK: - Private

    private let eventStore = EKEventStore()

    // MARK: - Public API

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let events: () = loadCalendarEvents()
        async let reminders: () = loadReminders()
        _ = await (events, reminders)
    }

    // MARK: - Calendar Events

    private func loadCalendarEvents() async {
        let status = EKEventStore.authorizationStatus(for: .event)
        guard status == .fullAccess || status == .authorized else {
            #if DEBUG
            print("[InternalTab] Calendar access not authorized: \(status.rawValue)")
            #endif
            return
        }

        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else { return }

        let predicate = eventStore.predicateForEvents(withStart: startOfDay, end: endOfDay, calendars: nil)
        let events = eventStore.events(matching: predicate)
        todayEvents = events.sorted { ($0.startDate ?? .distantPast) < ($1.startDate ?? .distantPast) }
    }

    // MARK: - Reminders

    private func loadReminders() async {
        let status = EKEventStore.authorizationStatus(for: .reminder)
        guard status == .fullAccess || status == .authorized else {
            #if DEBUG
            print("[InternalTab] Reminders access not authorized: \(status.rawValue)")
            #endif
            return
        }

        let predicate = eventStore.predicateForReminders(in: nil)
        let allReminders = await withCheckedContinuation { continuation in
            eventStore.fetchReminders(matching: predicate) { reminders in
                continuation.resume(returning: reminders ?? [])
            }
        }

        let calendar = Calendar.current
        let now = Date()
        let startOfDay = calendar.startOfDay(for: now)
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else { return }

        // Include reminders due today or overdue + incomplete
        todayReminders = allReminders.filter { reminder in
            guard !reminder.isCompleted else { return false }
            guard let dueDate = reminder.dueDateComponents?.date else { return false }
            // Due today or overdue
            return dueDate < endOfDay
        }
    }
}
