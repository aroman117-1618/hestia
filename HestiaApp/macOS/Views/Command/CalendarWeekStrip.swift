import SwiftUI
import EventKit

struct CalendarWeekStrip: View {
    let events: [EKEvent]
    @State private var weekOffset: Int = 0

    private var weekDates: [Date] {
        let calendar = Calendar.current
        let startOfWeek = calendar.date(from: calendar.dateComponents([.yearForWeekOfYear, .weekOfYear], from: Date())) ?? Date()
        let adjusted = calendar.date(byAdding: .weekOfYear, value: weekOffset, to: startOfWeek) ?? startOfWeek
        return (0..<7).compactMap { calendar.date(byAdding: .day, value: $0, to: adjusted) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header: date range + nav
            HStack {
                Text(weekRangeText)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                HStack(spacing: MacSpacing.sm) {
                    Button { withAnimation { weekOffset -= 1 } } label: {
                        Image(systemName: "chevron.left")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textSecondary)
                            .frame(width: 26, height: 26)
                    }
                    .buttonStyle(.hestiaIcon)
                    .accessibilityLabel("Previous week")
                    .hoverCursor(.pointingHand)

                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "calendar")
                            .font(MacTypography.smallBody)
                            .foregroundStyle(MacColors.textSecondary)
                        Text("This Week")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    Button { withAnimation { weekOffset += 1 } } label: {
                        Image(systemName: "chevron.right")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textSecondary)
                            .frame(width: 26, height: 26)
                    }
                    .buttonStyle(.hestiaIcon)
                    .accessibilityLabel("Next week")
                    .hoverCursor(.pointingHand)
                }
            }

            // Day columns
            HStack(spacing: 0) {
                ForEach(weekDates, id: \.self) { date in
                    dayColumn(date: date)
                        .frame(maxWidth: .infinity)
                }
            }

            // Legend
            legendRow
        }
        .padding(MacSpacing.xl)
        .hestiaPanel()
    }

    private func dayColumn(date: Date) -> some View {
        let calendar = Calendar.current
        let isToday = calendar.isDateInToday(date)
        let dayEvents = events.filter { calendar.isDate($0.startDate, inSameDayAs: date) }

        return VStack(spacing: MacSpacing.sm) {
            Text(date.formatted(.dateTime.weekday(.abbreviated)))
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textSecondary)

            ZStack {
                if isToday {
                    Circle()
                        .fill(MacColors.amberAccent.opacity(0.3))
                        .frame(width: MacSize.activeDayCircle, height: MacSize.activeDayCircle)
                }
                Text(date.formatted(.dateTime.day()))
                    .font(MacTypography.label)
                    .foregroundStyle(isToday ? MacColors.textPrimary : MacColors.textSecondary)
            }
            .frame(height: MacSize.activeDayCircle)

            // Event dots
            HStack(spacing: MacSpacing.xs) {
                ForEach(0..<min(dayEvents.count, 3), id: \.self) { index in
                    Circle()
                        .fill(eventColor(dayEvents[index]))
                        .frame(width: MacSize.eventDotSize, height: MacSize.eventDotSize)
                }
            }
            .frame(height: MacSize.eventDotSize + 2)
        }
    }

    private var legendRow: some View {
        HStack(spacing: MacSpacing.lg) {
            legendItem("Alert", color: MacColors.healthRed)
            legendItem("Insight", color: MacColors.amberAccent)
            legendItem("News", color: MacColors.amberBright)
            legendItem("Order", color: MacColors.healthGreen)
            legendItem("Event", color: MacColors.blueAccent)
            legendItem("Task", color: MacColors.textSecondary)
        }
    }

    private func legendItem(_ label: String, color: Color) -> some View {
        HStack(spacing: MacSpacing.xs) {
            Circle()
                .fill(color)
                .frame(width: MacSize.eventDotSize, height: MacSize.eventDotSize)
            Text(label)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var weekRangeText: String {
        guard let first = weekDates.first, let last = weekDates.last else { return "" }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return "\(formatter.string(from: first)) – \(formatter.string(from: last))"
    }

    private func eventColor(_ event: EKEvent) -> Color {
        if let cgColor = event.calendar?.cgColor {
            return Color(cgColor: cgColor)
        }
        return MacColors.amberAccent
    }
}
