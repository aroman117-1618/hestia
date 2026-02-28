import SwiftUI
import HestiaShared

/// Card showing the next upcoming meeting from the calendar
struct NextMeetingCard: View {
    let event: CalendarEvent?
    let isLoading: Bool

    @State private var currentTime = Date()

    /// Timer for updating the countdown
    private let countdownTimer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()

    init(event: CalendarEvent? = nil, isLoading: Bool = false) {
        self.event = event
        self.isLoading = isLoading
    }

    /// Legacy initializer for backward compatibility
    init(meeting: Meeting) {
        self.event = CalendarEvent(
            id: meeting.id,
            title: meeting.title,
            startTime: meeting.startsAt,
            endTime: meeting.startsAt.addingTimeInterval(3600),
            isAllDay: false,
            calendarName: "Calendar",
            location: meeting.location
        )
        self.isLoading = false
    }

    var body: some View {
        Group {
            if let event = event {
                eventCard(event: event)
            } else if isLoading {
                loadingCard
            }
            // When no event exists, this card is not shown - parent handles empty state
        }
    }

    // MARK: - Event Card

    private func eventCard(event: CalendarEvent) -> some View {
        HStack(spacing: Spacing.md) {
            // Calendar icon
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.white.opacity(0.2))
                    .frame(width: 50, height: 50)

                Image(systemName: "calendar")
                    .font(.system(size: 24))
                    .foregroundColor(.white)
            }

            // Event details
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(event.title)
                    .cardTitleStyle()
                    .lineLimit(1)

                HStack(spacing: Spacing.sm) {
                    // Time indicator with dynamic countdown
                    Label {
                        Text(event.formattedCountdown)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.7))
                    } icon: {
                        Image(systemName: "clock")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.7))
                    }

                    if let location = event.location, !location.isEmpty {
                        Text("\u{2022}")
                            .foregroundColor(.white.opacity(0.5))

                        Label {
                            Text(location)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                                .lineLimit(1)
                        } icon: {
                            Image(systemName: "location")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                        }
                    }
                }
            }

            Spacer()

            // Chevron
            Image(systemName: "chevron.right")
                .foregroundColor(.white.opacity(0.5))
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Next event: \(event.title) \(event.formattedCountdown)")
        .onReceive(countdownTimer) { _ in
            // Force view refresh for countdown update
            currentTime = Date()
        }
    }

    // MARK: - Loading Card

    private var loadingCard: some View {
        HStack(spacing: Spacing.md) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.white.opacity(0.1))
                    .frame(width: 50, height: 50)

                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
            }

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Loading calendar...")
                    .font(.cardTitle)
                    .foregroundColor(.white.opacity(0.5))
            }

            Spacer()
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }
}

// MARK: - Empty State View (Open Horizon with Quote)

struct CalendarEmptyStateView: View {
    /// Pool of quotes for empty calendar state
    private let quotes = [
        "....the silence is almost eerie",
        "breathe it in...",
        "maybe they forgot to tell you?",
        "where's the fire?",
        ".......*burps*.......",
        "to live is to risk it all; otherwise you're just an inert chunk of randomly assembled molecules drifting wherever the universe blows you.",
        "have fun with empowerment. It seems to make everyone that gets it really happy.",
        "if I die in a cage, I lose a bet.",
        "there's a lesson here, and I'm not going to be the one to figure it out.",
        "your boos mean nothing, I've seen what makes you cheer"
    ]

    /// Get a quote that changes daily
    private var dailyQuote: String {
        let dayOfYear = Calendar.current.ordinality(of: .day, in: .year, for: Date()) ?? 0
        let index = dayOfYear % quotes.count
        return quotes[index]
    }

    var body: some View {
        VStack(spacing: Spacing.lg) {
            // Open horizon visual
            ZStack {
                // Gradient background representing open sky/horizon
                LinearGradient(
                    colors: [
                        Color(hex: "1a1a2e").opacity(0.8),
                        Color(hex: "16213e").opacity(0.6),
                        Color(hex: "0f3460").opacity(0.4)
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .frame(height: 120)
                .cornerRadius(CornerRadius.card)

                // Subtle horizon line
                VStack {
                    Spacer()
                    Rectangle()
                        .fill(
                            LinearGradient(
                                colors: [.clear, Color.white.opacity(0.1), .clear],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(height: 1)
                        .padding(.bottom, 40)
                }

                // Quote overlay
                VStack(spacing: Spacing.sm) {
                    Text("No upcoming events")
                        .font(.headline)
                        .foregroundColor(.white.opacity(0.8))

                    Text("\"\(dailyQuote)\"")
                        .font(.subheadline)
                        .italic()
                        .foregroundColor(.white.opacity(0.5))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, Spacing.md)
                }
            }
        }
        .padding(.horizontal, Spacing.lg)
    }
}

// MARK: - Preview

struct NextMeetingCard_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: Spacing.lg) {
                // With event
                NextMeetingCard(
                    event: CalendarEvent.mockEvent,
                    isLoading: false
                )

                // Loading
                NextMeetingCard(
                    event: nil,
                    isLoading: true
                )

                // Empty state
                CalendarEmptyStateView()
            }
        }
    }
}
