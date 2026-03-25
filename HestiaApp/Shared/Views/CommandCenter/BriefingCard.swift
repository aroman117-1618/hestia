import SwiftUI
import HestiaShared

/// Collapsible daily briefing card displayed above the timeline
struct BriefingCard: View {
    let briefing: BriefingResponse?
    let isLoading: Bool
    @Binding var isExpanded: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header (always visible)
            Button {
                withAnimation(.hestiaQuick) {
                    isExpanded.toggle()
                }
            } label: {
                headerContent
            }
            .buttonStyle(.plain)

            // Expandable content
            if isExpanded, let briefing = briefing {
                expandedContent(briefing)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Header

    private var headerContent: some View {
        HStack {
            Image(systemName: "sun.max.fill")
                .font(.title3)
                .foregroundColor(.warningYellow)

            VStack(alignment: .leading, spacing: 2) {
                if let briefing = briefing {
                    Text(briefing.greeting)
                        .font(.headline)
                        .foregroundColor(.textPrimary)
                } else if isLoading {
                    Text("Loading briefing...")
                        .font(.headline)
                        .foregroundColor(.textSecondary)
                } else {
                    Text("Daily Briefing")
                        .font(.headline)
                        .foregroundColor(.textPrimary)
                }

                if let briefing = briefing {
                    Text(briefingSummary(briefing))
                        .font(.caption)
                        .foregroundColor(.textSecondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                .font(.caption)
                .foregroundColor(.textTertiary)
        }
        .padding(Spacing.md)
    }

    // MARK: - Expanded Content

    private func expandedContent(_ briefing: BriefingResponse) -> some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Divider()
                .background(Color.bgOverlay)

            // Briefing text
            if !briefing.text.isEmpty {
                Text(briefing.text)
                    .font(.subheadline)
                    .foregroundColor(.textPrimary.opacity(0.8))
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Quick stats row
            HStack(spacing: Spacing.lg) {
                if briefing.hasCalendarEvents {
                    statBadge(
                        icon: "calendar",
                        count: briefing.calendar.count,
                        label: "events"
                    )
                }

                if briefing.hasReminders {
                    statBadge(
                        icon: "checklist",
                        count: briefing.reminders.count,
                        label: "reminders"
                    )
                }

                if briefing.tasks.count > 0 {
                    statBadge(
                        icon: "list.bullet",
                        count: briefing.tasks.count,
                        label: "tasks"
                    )
                }
            }

            // Suggestions
            if !briefing.suggestions.isEmpty {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Suggestions")
                        .font(.caption.weight(.semibold))
                        .foregroundColor(.textSecondary)

                    ForEach(briefing.suggestions, id: \.self) { suggestion in
                        HStack(alignment: .top, spacing: Spacing.xs) {
                            Image(systemName: "lightbulb.fill")
                                .font(.caption2)
                                .foregroundColor(.warningYellow)
                            Text(suggestion)
                                .font(.caption)
                                .foregroundColor(.textSecondary)
                        }
                    }
                }
            }
        }
        .padding(.horizontal, Spacing.md)
        .padding(.bottom, Spacing.md)
    }

    // MARK: - Helpers

    private func statBadge(icon: String, count: Int, label: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
            Text("\(count) \(label)")
                .font(.caption)
        }
        .foregroundColor(.textSecondary)
    }

    private func briefingSummary(_ briefing: BriefingResponse) -> String {
        var parts: [String] = []
        if briefing.calendar.count > 0 {
            parts.append("\(briefing.calendar.count) event\(briefing.calendar.count == 1 ? "" : "s")")
        }
        if briefing.reminders.count > 0 {
            parts.append("\(briefing.reminders.count) reminder\(briefing.reminders.count == 1 ? "" : "s")")
        }
        if parts.isEmpty { return "No upcoming items" }
        return parts.joined(separator: " · ")
    }
}
