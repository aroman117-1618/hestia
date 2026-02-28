import SwiftUI
import HestiaShared

struct StatCardsRow: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    private let cards: [(icon: String, label: String, count: String, subtitle: String, trend: String?)] = [
        ("bell.badge", "Alerts", "2", "unread", nil),
        ("lightbulb", "Insights", "2", "total", "+2"),
        ("newspaper", "News", "2", "articles", nil),
        ("bolt.circle", "Orders", "2", "active", nil),
        ("calendar", "Events", "2", "upcoming", nil),
        ("checklist", "Tasks", "1", "pending", "+1")
    ]

    var body: some View {
        HStack(spacing: MacSpacing.md) {
            ForEach(cards, id: \.label) { card in
                StatCard(
                    icon: card.icon,
                    label: card.label,
                    count: card.count,
                    subtitle: card.subtitle,
                    trendValue: card.trend
                )
            }
        }
    }
}

struct StatCard: View {
    let icon: String
    let label: String
    let count: String
    let subtitle: String
    let trendValue: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Icon + trend badge
            HStack {
                ZStack {
                    Circle()
                        .fill(MacColors.searchInputBackground)
                        .frame(width: MacSize.statCardIconCircle, height: MacSize.statCardIconCircle)
                    Image(systemName: icon)
                        .font(.system(size: MacSize.navIcon))
                        .foregroundStyle(MacColors.amberAccent)
                }

                Spacer()

                if let trend = trendValue {
                    TrendBadge(trend)
                }
            }
            .padding(.bottom, MacSpacing.md)

            // Label
            Text(label)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
                .padding(.bottom, MacSpacing.sm)

            // Count + subtitle
            HStack(alignment: .firstTextBaseline, spacing: MacSpacing.sm) {
                Text(count)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(MacColors.textPrimary)
                Text(subtitle)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }
        }
        .padding(17)
        .frame(maxWidth: .infinity)
        .frame(height: MacSize.statCardHeight)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }
}
