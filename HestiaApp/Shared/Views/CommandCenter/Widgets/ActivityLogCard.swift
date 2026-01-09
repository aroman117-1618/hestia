import SwiftUI

/// Card showing a single activity log entry
struct ActivityLogCard: View {
    let activity: Activity

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Colored icon
            ZStack {
                Circle()
                    .fill(Color(hex: activity.color))
                    .frame(width: 40, height: 40)

                Image(systemName: activity.icon)
                    .font(.system(size: 18))
                    .foregroundColor(.white)
            }

            // Activity details
            VStack(alignment: .leading, spacing: 2) {
                Text(activity.title)
                    .cardTitleStyle()

                Text(activity.subtitle)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()

            // Timestamp
            Text(activity.formattedTime)
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(activity.title), \(activity.subtitle), at \(activity.formattedTime)")
    }
}

// MARK: - System Health Card

struct SystemHealthCard: View {
    let health: SystemHealth

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Header
            HStack {
                Image(systemName: health.status.iconName)
                    .foregroundColor(health.status.color)

                Text("System Status")
                    .cardTitleStyle()

                Spacer()

                Text(health.status.displayText)
                    .font(.caption)
                    .foregroundColor(health.status.color)
            }

            // Component grid
            HStack(spacing: Spacing.md) {
                ComponentIndicator(
                    name: "Inference",
                    status: health.components.inference.status
                )

                ComponentIndicator(
                    name: "Memory",
                    status: health.components.memory.status
                )

                ComponentIndicator(
                    name: "Tools",
                    status: health.components.tools.status
                )
            }
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }
}

/// Small component status indicator
struct ComponentIndicator: View {
    let name: String
    let status: HealthStatus

    var body: some View {
        VStack(spacing: Spacing.xs) {
            Circle()
                .fill(status.color)
                .frame(width: 10, height: 10)

            Text(name)
                .font(.caption2)
                .foregroundColor(.white.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Preview

struct ActivityLogCard_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: Spacing.md) {
                ActivityLogCard(activity: Activity(
                    id: "1",
                    title: "Drafted Email Response",
                    subtitle: "Re: Q4 Budget Review",
                    icon: "envelope.fill",
                    color: "FF6B6B",
                    timestamp: Date()
                ))

                ActivityLogCard(activity: Activity(
                    id: "2",
                    title: "Stock Tip: KVYO",
                    subtitle: "Price alert triggered",
                    icon: "chart.bar.fill",
                    color: "FFD93D",
                    timestamp: Date().addingTimeInterval(-3600)
                ))

                SystemHealthCard(health: SystemHealth.mockHealthy)
            }
            .padding()
        }
    }
}
