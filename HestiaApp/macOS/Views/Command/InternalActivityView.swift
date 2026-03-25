import SwiftUI
import HestiaShared
import EventKit

// MARK: - Internal Activity Tab

struct InternalActivityView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.lg) {
                // Health Summary
                CollapsibleSection(
                    title: "Health Summary",
                    icon: "heart.fill"
                ) {
                    healthContent
                }

                // Today's Calendar Events
                CollapsibleSection(
                    title: "Upcoming Events",
                    icon: "calendar",
                    count: viewModel.calendarEvents.count
                ) {
                    calendarContent
                }
            }
            .padding(.top, MacSpacing.lg)
        }
    }

    // MARK: - Health Summary

    @ViewBuilder
    private var healthContent: some View {
        if let summary = viewModel.healthSummary {
            HStack(spacing: MacSpacing.md) {
                healthMetricCard(
                    icon: "figure.walk",
                    label: "Steps",
                    value: formattedSteps(summary),
                    color: MacColors.healthGreen
                )
                healthMetricCard(
                    icon: "heart.fill",
                    label: "Resting HR",
                    value: formattedHeartRate(summary),
                    color: MacColors.healthRed
                )
                healthMetricCard(
                    icon: "bed.double.fill",
                    label: "Sleep",
                    value: formattedSleep(summary),
                    color: MacColors.sleepPurple
                )
            }
        } else {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "heart.slash")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textSecondary.opacity(0.5))
                Text("Health data unavailable — check HealthKit permissions")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(MacSpacing.md)
        }
    }

    private func healthMetricCard(icon: String, label: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: icon)
                    .font(MacTypography.smallBody)
                    .foregroundStyle(color)
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
            Text(value)
                .font(MacTypography.pageTitle)
                .foregroundStyle(MacColors.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Calendar Events

    @ViewBuilder
    private var calendarContent: some View {
        if viewModel.calendarEvents.isEmpty {
            VStack(spacing: MacSpacing.sm) {
                Image(systemName: "calendar.badge.checkmark")
                    .font(MacTypography.pageTitle)
                    .foregroundStyle(MacColors.textSecondary.opacity(0.5))
                Text("No upcoming events")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, MacSpacing.xl)
        } else {
            VStack(spacing: MacSpacing.sm) {
                ForEach(viewModel.calendarEvents.prefix(5), id: \.eventIdentifier) { event in
                    calendarEventRow(event)
                }
            }
        }
    }

    private func calendarEventRow(_ event: EKEvent) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Time column
            VStack(spacing: 0) {
                Text(event.startDate, style: .time)
                    .font(MacTypography.code)
                    .foregroundStyle(MacColors.amberAccent)
            }
            .frame(width: 55, alignment: .trailing)

            // Colored bar
            RoundedRectangle(cornerRadius: 1.5)
                .fill(calendarColor(event))
                .frame(width: 3, height: 32)

            // Event info
            VStack(alignment: .leading, spacing: 2) {
                Text(event.title ?? "Untitled")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                if let location = event.location, !location.isEmpty {
                    Text(location)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            // Duration
            Text(durationLabel(event))
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Helpers

    private func formattedSteps(_ summary: MacHealthSummaryResponse) -> String {
        // Backend key: "stepCount" — nested: {"value": N, "samples": N}
        // AnyCodableValue.doubleValue extracts from nested {"value": N}
        if let steps = summary.double(from: summary.activity, key: "stepCount") {
            return "\(Int(steps))"
        }
        return "—"
    }

    private func formattedHeartRate(_ summary: MacHealthSummaryResponse) -> String {
        // Backend key: "restingHeartRate" — nested: {"avg": N, "min": N, "max": N}
        // AnyCodableValue.doubleValue extracts from nested {"avg": N}
        if let hr = summary.double(from: summary.heart, key: "restingHeartRate") {
            return "\(Int(hr)) bpm"
        }
        return "—"
    }

    private func formattedSleep(_ summary: MacHealthSummaryResponse) -> String {
        // Backend key: "total_hours" — scalar float
        if let hours = summary.double(from: summary.sleep, key: "total_hours") {
            let h = Int(hours)
            let m = Int((hours - Double(h)) * 60)
            return "\(h)h \(m)m"
        }
        return "—"
    }

    private func calendarColor(_ event: EKEvent) -> Color {
        if let cgColor = event.calendar?.cgColor {
            return Color(cgColor: cgColor)
        }
        return MacColors.amberAccent
    }

    private func durationLabel(_ event: EKEvent) -> String {
        let minutes = Int(event.endDate.timeIntervalSince(event.startDate) / 60)
        if minutes >= 60 {
            let h = minutes / 60
            let m = minutes % 60
            return m > 0 ? "\(h)h \(m)m" : "\(h)h"
        }
        return "\(minutes)m"
    }
}
