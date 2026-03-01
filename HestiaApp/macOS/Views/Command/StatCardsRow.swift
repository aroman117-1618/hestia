import SwiftUI
import HestiaShared

struct StatCardsRow: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    private var cards: [(icon: String, label: String, count: String, subtitle: String, trend: String?)] {
        [
            ("bell.badge", "Unread", "\(viewModel.unreadCount)", "items", nil),
            ("brain", "Memory", "\(viewModel.pendingMemoryCount)", "pending", nil),
            ("bolt.circle", "Orders", "\(viewModel.activeOrderCount)", "active", nil),
            ("calendar", "Events", "\(viewModel.todayEventCount)", "upcoming", nil),
            ("heart.fill", "Health", viewModel.healthStatus, "", nil),
            ("newspaper", "Feed", "\(viewModel.newsfeedItems.count)", "items", nil)
        ]
    }

    private let columns = Array(repeating: GridItem(.flexible(), spacing: MacSpacing.md), count: 3)

    var body: some View {
        LazyVGrid(columns: columns, spacing: MacSpacing.md) {
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
                    .lineLimit(1)
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
