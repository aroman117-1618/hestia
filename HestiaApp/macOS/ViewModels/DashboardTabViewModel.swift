import SwiftUI
import EventKit
import HestiaShared

/// ViewModel for the Dashboard sub-tab of Command Center.
/// Aggregates health summary, calendar events (2-week range), reminders, and trading data.
@MainActor
class DashboardTabViewModel: ObservableObject {

    // MARK: - Lookback Period

    enum LookbackPeriod: String, CaseIterable, Identifiable {
        case twentyFourHour = "1D"
        case sevenDay = "7D"
        case thirtyDay = "30D"
        case all = "ALL"

        var id: String { rawValue }

        var displayName: String { rawValue }
    }

    // MARK: - Published State

    @Published var healthSummary: MacHealthSummaryResponse?
    @Published var calendarEvents: [EKEvent] = []
    @Published var currentWeekStart: Date = Calendar.startOfWeek(for: Date())
    @Published var reminders: [EKReminder] = []
    @Published var tradingSummary: TradingSummary?
    @Published var bots: [TradingBotResponse] = []
    @Published var lookbackPeriod: LookbackPeriod = .twentyFourHour {
        didSet {
            guard lookbackPeriod != oldValue else { return }
            Task { await loadTrading() }
        }
    }
    @Published var isLoading = false

    // MARK: - Computed Properties

    /// Incomplete reminders with due date before now.
    var overdueReminders: [EKReminder] {
        let now = Date()
        return reminders.filter { reminder in
            guard !reminder.isCompleted else { return false }
            guard let dueDate = reminder.dueDateComponents?.date else { return false }
            return dueDate < now
        }
    }

    /// Incomplete reminders with due date >= now.
    var currentReminders: [EKReminder] {
        let now = Date()
        return reminders.filter { reminder in
            guard !reminder.isCompleted else { return false }
            guard let dueDate = reminder.dueDateComponents?.date else { return false }
            return dueDate >= now
        }
    }

    /// Reminders completed today (for strikethrough display).
    var completedReminders: [EKReminder] {
        reminders.filter { $0.isCompleted }
    }

    /// Events occurring today.
    var todayEvents: [EKEvent] {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else { return [] }
        return calendarEvents.filter { event in
            guard let start = event.startDate, let end = event.endDate else { return false }
            return start < endOfDay && end > startOfDay
        }
    }

    /// Start and end dates for the 2-week calendar range.
    var twoWeekRange: (start: Date, end: Date) {
        let start = currentWeekStart
        let end = Calendar.current.date(byAdding: .day, value: 14, to: start) ?? start
        return (start, end)
    }

    /// Number of bots with status "running".
    var activeBotCount: Int {
        bots.filter { $0.status == "running" }.count
    }

    // MARK: - Private

    private let eventStore = EKEventStore()

    // MARK: - Public API

    /// Parallel load of health, calendar, reminders, and trading data.
    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let health: () = loadHealth()
        async let calendar: () = loadCalendarEvents()
        async let fetchReminders: () = loadReminders()
        async let trading: () = loadTrading()
        _ = await (health, calendar, fetchReminders, trading)
    }

    /// Shift the current week start by +/- 7 days and reload calendar events.
    func navigateWeek(forward: Bool) {
        guard let newStart = Calendar.current.date(
            byAdding: .day,
            value: forward ? 7 : -7,
            to: currentWeekStart
        ) else { return }
        currentWeekStart = newStart
        Task {
            await loadCalendarEvents()
        }
    }

    /// Activate the kill switch for all bots, then reload trading data.
    func killAllBots() async {
        do {
            _ = try await APIClient.shared.activateKillSwitch(reason: "Manual kill from Dashboard")
        } catch {
            #if DEBUG
            print("[DashboardTab] Kill switch failed: \(error)")
            #endif
        }
        await loadTrading()
    }

    // MARK: - Private Loaders

    private func loadHealth() async {
        let (summary, _) = await CacheFetcher.load(
            key: CacheKey.healthSummary,
            ttl: CacheTTL.standard
        ) {
            try await APIClient.shared.getHealthSummary()
        }
        healthSummary = summary
    }

    private func loadCalendarEvents() async {
        let status = EKEventStore.authorizationStatus(for: .event)
        guard status == .fullAccess || status == .authorized else {
            #if DEBUG
            print("[DashboardTab] Calendar access not authorized: \(status.rawValue)")
            #endif
            return
        }

        let range = twoWeekRange
        let predicate = eventStore.predicateForEvents(withStart: range.start, end: range.end, calendars: nil)
        let events = eventStore.events(matching: predicate)
        calendarEvents = events.sorted { ($0.startDate ?? .distantPast) < ($1.startDate ?? .distantPast) }
    }

    private func loadReminders() async {
        let status = EKEventStore.authorizationStatus(for: .reminder)
        if status == .notDetermined {
            await requestReminderAccess()
            return
        }
        guard status == .fullAccess || status == .authorized else {
            #if DEBUG
            print("[DashboardTab] Reminders access not authorized: \(status.rawValue)")
            #endif
            return
        }

        let store = eventStore
        let predicate = store.predicateForReminders(in: nil)

        // EKReminder is not Sendable — use nonisolated helper to bridge
        let allReminders: [EKReminder] = await withCheckedContinuation { continuation in
            store.fetchReminders(matching: predicate) { reminders in
                nonisolated(unsafe) let result = reminders ?? []
                continuation.resume(returning: result)
            }
        }

        // Keep incomplete reminders + those completed today (for strikethrough display)
        let today = Calendar.current.startOfDay(for: Date())
        reminders = allReminders.filter { reminder in
            if !reminder.isCompleted { return true }
            guard let completed = reminder.completionDate else { return false }
            return completed >= today
        }
    }

    private func requestReminderAccess() async {
        do {
            if #available(macOS 14.0, *) {
                let granted = try await eventStore.requestFullAccessToReminders()
                if granted { await loadReminders() }
            } else {
                let granted = try await eventStore.requestAccess(to: .reminder)
                if granted { await loadReminders() }
            }
        } catch {
            #if DEBUG
            print("[DashboardTab] Reminder access denied: \(error)")
            #endif
        }
    }

    private func loadTrading() async {
        let (summary, _) = await CacheFetcher.load(
            key: CacheKey.tradingSummary,
            ttl: CacheTTL.realtime
        ) {
            try await APIClient.shared.getTradingSummary(period: self.lookbackPeriod.rawValue)
        }
        tradingSummary = summary

        let (botsResponse, _) = await CacheFetcher.load(
            key: CacheKey.tradingBots,
            ttl: CacheTTL.frequent
        ) {
            try await APIClient.shared.getTradingBots()
        }
        bots = botsResponse?.bots ?? []
    }
}

// MARK: - Calendar Extension

extension Calendar {
    /// Returns the Monday of the week containing the given date.
    static func startOfWeek(for date: Date) -> Date {
        let calendar = Calendar.current
        var components = calendar.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date)
        // ISO 8601: Monday = 2 in Calendar. Setting weekday ensures Monday.
        components.weekday = 2
        return calendar.date(from: components) ?? calendar.startOfDay(for: date)
    }
}
