import Foundation

/// A calendar event from EventKit
struct CalendarEvent: Identifiable, Equatable {
    let id: String
    let title: String
    let startTime: Date
    let endTime: Date
    let isAllDay: Bool
    let calendarName: String
    let location: String?

    // MARK: - Computed Properties

    /// Time until the event starts
    var timeUntilStart: TimeInterval {
        startTime.timeIntervalSinceNow
    }

    /// Whether the event is in the past
    var isPast: Bool {
        timeUntilStart < 0
    }

    /// Whether the event is currently happening
    var isOngoing: Bool {
        let now = Date()
        return startTime <= now && now <= endTime
    }

    /// Duration of the event in minutes
    var durationMinutes: Int {
        Int(endTime.timeIntervalSince(startTime) / 60)
    }

    /// Formatted countdown string
    var formattedCountdown: String {
        let seconds = timeUntilStart

        if seconds < 0 {
            if isOngoing {
                return "Now"
            }
            return "Past"
        }

        let minutes = Int(seconds / 60)
        let hours = Int(seconds / 3600)
        let days = Int(seconds / 86400)

        if days > 0 {
            return days == 1 ? "in 1 day" : "in \(days) days"
        } else if hours > 0 {
            let remainingMinutes = minutes % 60
            if remainingMinutes > 0 && hours < 3 {
                return "in \(hours)h \(remainingMinutes)m"
            }
            return hours == 1 ? "in 1 hour" : "in \(hours) hours"
        } else if minutes > 0 {
            return minutes == 1 ? "in 1 minute" : "in \(minutes) minutes"
        } else {
            return "Starting now"
        }
    }

    /// Formatted time range string
    var formattedTimeRange: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short

        if isAllDay {
            return "All Day"
        }

        return "\(formatter.string(from: startTime)) - \(formatter.string(from: endTime))"
    }

    /// Formatted date string
    var formattedDate: String {
        let formatter = DateFormatter()
        let calendar = Calendar.current

        if calendar.isDateInToday(startTime) {
            return "Today"
        } else if calendar.isDateInTomorrow(startTime) {
            return "Tomorrow"
        } else {
            formatter.dateStyle = .medium
            return formatter.string(from: startTime)
        }
    }
}

// MARK: - Mock Data

extension CalendarEvent {
    static let mockEvent = CalendarEvent(
        id: "mock-1",
        title: "Meeting with Gavin",
        startTime: Date().addingTimeInterval(12 * 60),
        endTime: Date().addingTimeInterval(72 * 60),
        isAllDay: false,
        calendarName: "Work",
        location: "Conference Room A"
    )

    static let mockEvents: [CalendarEvent] = [
        mockEvent,
        CalendarEvent(
            id: "mock-2",
            title: "Team Standup",
            startTime: Date().addingTimeInterval(3 * 3600),
            endTime: Date().addingTimeInterval(3.5 * 3600),
            isAllDay: false,
            calendarName: "Work",
            location: "Zoom"
        ),
        CalendarEvent(
            id: "mock-3",
            title: "Dentist Appointment",
            startTime: Calendar.current.date(byAdding: .day, value: 1, to: Date())!,
            endTime: Calendar.current.date(byAdding: .day, value: 1, to: Date())!.addingTimeInterval(3600),
            isAllDay: false,
            calendarName: "Personal",
            location: "Dr. Smith's Office"
        )
    ]
}
