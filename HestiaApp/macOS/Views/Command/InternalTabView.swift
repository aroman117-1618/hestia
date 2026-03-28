import SwiftUI
import EventKit

struct InternalTabView: View {
    @StateObject private var viewModel = InternalTabViewModel()

    private let cardBackground = Color(red: 17/255, green: 11/255, blue: 3/255)
    private let cardBorder = Color(red: 26/255, green: 20/255, blue: 8/255)

    var body: some View {
        ScrollView {
            HStack(alignment: .top, spacing: MacSpacing.md) {
                calendarCard
                tasksCard
            }
            .padding(MacSpacing.md)
        }
        .task {
            await viewModel.loadData()
        }
    }

    // MARK: - Calendar Card (Left)

    private var calendarCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(MacColors.statusInfo)
                    .frame(width: 8, height: 8)
                Text("Calendar")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
            }

            // Week strip
            weekStrip

            // Event list
            if viewModel.todayEvents.isEmpty {
                emptyState(icon: "calendar", message: "No events today")
            } else {
                VStack(spacing: 0) {
                    ForEach(viewModel.todayEvents, id: \.eventIdentifier) { event in
                        eventRow(event)
                        if event.eventIdentifier != viewModel.todayEvents.last?.eventIdentifier {
                            Divider()
                                .background(MacColors.divider)
                        }
                    }
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(cardBackground)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(cardBorder, lineWidth: 1)
        )
    }

    // MARK: - Week Strip

    private var weekStrip: some View {
        let calendar = Calendar.current
        let today = Date()
        let weekday = calendar.component(.weekday, from: today)
        // weekday: 1=Sun, we want Mon-Sun
        let mondayOffset = weekday == 1 ? -6 : (2 - weekday)
        let monday = calendar.date(byAdding: .day, value: mondayOffset, to: today)!

        return HStack(spacing: 2) {
            ForEach(0..<7, id: \.self) { offset in
                let day = calendar.date(byAdding: .day, value: offset, to: monday)!
                let isToday = calendar.isDateInToday(day)
                let dayLetter = ["M", "T", "W", "T", "F", "S", "S"][offset]
                let dayNumber = calendar.component(.day, from: day)

                VStack(spacing: 2) {
                    Text(dayLetter)
                        .font(.system(size: 9))
                        .foregroundStyle(isToday ? Color(red: 0.051, green: 0.031, blue: 0.008) : MacColors.textSecondary)
                    Text("\(dayNumber)")
                        .font(.system(size: 10, weight: isToday ? .semibold : .regular))
                        .foregroundStyle(isToday ? Color(red: 0.051, green: 0.031, blue: 0.008) : MacColors.textPrimary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, MacSpacing.xs)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(isToday ? MacColors.amberAccent : Color.clear)
                )
            }
        }
    }

    // MARK: - Event Row

    private func eventRow(_ event: EKEvent) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Text(formatTime(event.startDate))
                .font(.system(size: 11))
                .foregroundStyle(MacColors.statusInfo)
                .frame(width: 40, alignment: .leading)

            Text(event.title ?? "Untitled")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()

            Text(formatDuration(from: event.startDate, to: event.endDate))
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Tasks Card (Right)

    private var tasksCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(MacColors.amberAccent)
                    .frame(width: 8, height: 8)
                Text("Tasks & Reminders")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
            }

            // Task list
            if viewModel.todayReminders.isEmpty {
                emptyState(icon: "checkmark.circle", message: "All clear")
            } else {
                VStack(spacing: 0) {
                    ForEach(viewModel.todayReminders, id: \.calendarItemIdentifier) { reminder in
                        reminderRow(reminder)
                        if reminder.calendarItemIdentifier != viewModel.todayReminders.last?.calendarItemIdentifier {
                            Divider()
                                .background(MacColors.divider)
                        }
                    }
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(cardBackground)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(cardBorder, lineWidth: 1)
        )
    }

    // MARK: - Reminder Row

    private func reminderRow(_ reminder: EKReminder) -> some View {
        HStack(spacing: MacSpacing.sm) {
            // Checkbox
            ZStack {
                Circle()
                    .stroke(reminder.isCompleted ? Color.green : MacColors.textSecondary, lineWidth: 1.5)
                    .frame(width: 13, height: 13)

                if reminder.isCompleted {
                    Circle()
                        .fill(Color.green)
                        .frame(width: 13, height: 13)
                    Image(systemName: "checkmark")
                        .font(.system(size: 7, weight: .bold))
                        .foregroundStyle(.white)
                }
            }

            Text(reminder.title ?? "Untitled")
                .font(.system(size: 11))
                .foregroundStyle(reminder.isCompleted ? MacColors.textSecondary : MacColors.textPrimary)
                .strikethrough(reminder.isCompleted)
                .lineLimit(1)

            Spacer()

            if let dueDate = reminder.dueDateComponents?.date {
                Text(formatTime(dueDate))
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textSecondary)
            }
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Empty State

    private func emptyState(icon: String, message: String) -> some View {
        VStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundStyle(MacColors.textPlaceholder)
            Text(message)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPlaceholder)
        }
        .frame(maxWidth: .infinity, minHeight: 80)
    }

    // MARK: - Formatters

    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm"
        return formatter.string(from: date)
    }

    private func formatDuration(from start: Date, to end: Date) -> String {
        let minutes = Int(end.timeIntervalSince(start) / 60)
        if minutes < 60 {
            return "\(minutes)m"
        }
        let hours = minutes / 60
        let remaining = minutes % 60
        if remaining == 0 {
            return "\(hours)h"
        }
        return "\(hours)h \(remaining)m"
    }
}
