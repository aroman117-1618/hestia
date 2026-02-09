import Foundation
import EventKit
import Combine

/// Protocol for calendar service operations
protocol CalendarServiceProtocol {
    /// Request calendar access permission
    func requestAccess() async -> Bool

    /// Fetch the next upcoming event
    func fetchNextEvent(excluding calendars: [String], excludeAllDay: Bool) async -> CalendarEvent?

    /// Current authorization status
    var authorizationStatus: EKAuthorizationStatus { get }
}

/// Calendar service using EventKit for real device calendar access
@MainActor
final class CalendarService: ObservableObject, CalendarServiceProtocol {
    // MARK: - Published State

    @Published private(set) var nextEvent: CalendarEvent?
    @Published private(set) var isAuthorized: Bool = false
    @Published private(set) var isLoading: Bool = false

    // MARK: - Private Properties

    private let eventStore = EKEventStore()
    private var refreshTimer: Timer?

    /// Calendars to exclude from event fetching (reads from UserDefaults, falls back to default)
    private var excludedCalendars: [String] {
        UserDefaults.standard.stringArray(forKey: IntegrationKeys.calendarExcluded) ?? ["aLonati"]
    }

    // MARK: - Initialization

    nonisolated init() {
        // Authorization status will be updated on first access
    }

    /// Setup method to be called after init when on main actor
    func setup() {
        updateAuthorizationStatus()
    }

    nonisolated deinit {
        // Timer cleanup handled by system when reference is released
    }

    // MARK: - Public Properties

    nonisolated var authorizationStatus: EKAuthorizationStatus {
        EKEventStore.authorizationStatus(for: .event)
    }

    // MARK: - Public Methods

    /// Request calendar access permission
    func requestAccess() async -> Bool {
        do {
            if #available(iOS 17.0, *) {
                let granted = try await eventStore.requestFullAccessToEvents()
                await MainActor.run {
                    isAuthorized = granted
                }
                return granted
            } else {
                let granted = try await eventStore.requestAccess(to: .event)
                await MainActor.run {
                    isAuthorized = granted
                }
                return granted
            }
        } catch {
            #if DEBUG
            print("[CalendarService] Access request failed: \(error)")
            #endif
            return false
        }
    }

    /// Fetch the next upcoming event (excluding specified calendars and all-day events)
    func fetchNextEvent(excluding calendars: [String] = [], excludeAllDay: Bool = true) async -> CalendarEvent? {
        guard isAuthorized || authorizationStatus.isGranted else {
            return nil
        }

        isLoading = true
        defer { isLoading = false }

        let excludeList = calendars.isEmpty ? excludedCalendars : calendars

        // Search from now to 7 days in the future
        let startDate = Date()
        let endDate = Calendar.current.date(byAdding: .day, value: 7, to: startDate) ?? startDate

        // Get calendars to search (excluding specified ones)
        let allCalendars = eventStore.calendars(for: .event)
        let calendarsToSearch = allCalendars.filter { calendar in
            !excludeList.contains(calendar.title)
        }

        guard !calendarsToSearch.isEmpty else {
            return nil
        }

        // Create predicate
        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: calendarsToSearch
        )

        // Fetch events
        let events = eventStore.events(matching: predicate)

        // Filter and sort events
        let filteredEvents = events.filter { event in
            // Exclude all-day events if requested
            if excludeAllDay && event.isAllDay {
                return false
            }

            // Only include future events (not ones that have ended)
            if event.endDate < startDate {
                return false
            }

            return true
        }
        .sorted { $0.startDate < $1.startDate }

        // Get the next event
        guard let nextEKEvent = filteredEvents.first else {
            nextEvent = nil
            return nil
        }

        let calendarEvent = CalendarEvent(
            id: nextEKEvent.eventIdentifier,
            title: nextEKEvent.title ?? "Untitled Event",
            startTime: nextEKEvent.startDate,
            endTime: nextEKEvent.endDate,
            isAllDay: nextEKEvent.isAllDay,
            calendarName: nextEKEvent.calendar.title,
            location: nextEKEvent.location
        )

        nextEvent = calendarEvent
        return calendarEvent
    }

    /// Start auto-refresh timer for countdown updates
    func startAutoRefresh(interval: TimeInterval = 60) {
        stopAutoRefresh()

        refreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                _ = await self?.fetchNextEvent()
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
        isAuthorized = status.isGranted
    }
}

// MARK: - Mock Calendar Service for Previews

final class MockCalendarService: CalendarServiceProtocol {
    var authorizationStatus: EKAuthorizationStatus = .authorized

    func requestAccess() async -> Bool {
        return true
    }

    func fetchNextEvent(excluding calendars: [String], excludeAllDay: Bool) async -> CalendarEvent? {
        return CalendarEvent.mockEvent
    }
}

// MARK: - Extension for Auth Status Check

extension EKAuthorizationStatus {
    var isGranted: Bool {
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
