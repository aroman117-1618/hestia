import Foundation
import HestiaShared

extension Date {
    /// Format as time only (e.g., "3:45 PM")
    var timeString: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: self)
    }

    /// Format as date only (e.g., "Jan 15, 2025")
    var dateString: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: self)
    }

    /// Format as date and time
    var dateTimeString: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: self)
    }

    /// Relative time string (e.g., "5 minutes ago", "2 hours ago")
    var relativeString: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: self, relativeTo: Date())
    }

    /// Check if date is today
    var isToday: Bool {
        Calendar.current.isDateInToday(self)
    }

    /// Check if date is yesterday
    var isYesterday: Bool {
        Calendar.current.isDateInYesterday(self)
    }

    /// Check if date is in the current week
    var isThisWeek: Bool {
        Calendar.current.isDate(self, equalTo: Date(), toGranularity: .weekOfYear)
    }

    /// Minutes until this date (negative if in the past)
    var minutesFromNow: Int {
        let interval = self.timeIntervalSince(Date())
        return Int(interval / 60)
    }

    /// Human-readable "time until" string
    var timeUntilString: String {
        let minutes = minutesFromNow

        if minutes < 0 {
            return "\(abs(minutes)) minutes ago"
        } else if minutes == 0 {
            return "Now"
        } else if minutes < 60 {
            return "in \(minutes) minutes"
        } else if minutes < 1440 {
            let hours = minutes / 60
            return "in \(hours) hour\(hours == 1 ? "" : "s")"
        } else {
            let days = minutes / 1440
            return "in \(days) day\(days == 1 ? "" : "s")"
        }
    }
}

// MARK: - ISO 8601 Parsing

extension Date {
    /// Parse ISO 8601 date string
    static func fromISO8601(_ string: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: string)
    }

    /// Format as ISO 8601 string
    var iso8601String: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: self)
    }
}
