import SwiftUI
import HestiaShared

struct ActivityFeed: View {
    let orders: [OrderResponse]
    @State private var selectedFilter: String = "All Updates"
    @State private var searchText: String = ""

    private let filters = ["All Updates", "Alerts", "Insights", "News", "Orders", "Events", "Tasks"]

    // Mock feed items for UI layout
    private let feedItems: [(icon: String, iconColor: Color, description: String, metric: String?, time: String, hasDot: Bool)] = [
        ("shield", .red, "Security Monitoring: Threat Detector agent entered error state", "8.7%", "10 min ago", true),
        ("sparkles", .green, "E-commerce Recommendation Engine hit 99.2% accuracy", "99.2%", "15 min ago", true),
        ("newspaper", .orange, "OpenAI announces GPT-5 Turbo with 2x context window", nil, "30 min ago", true),
        ("bolt", .yellow, "Nightly data pipeline batch — scheduled run at 2:00 AM", nil, "1 hour ago", false),
        ("person.2", .blue, "Customer Support: Response time improved by 18%", "1.2s", "1 hour ago", false),
        ("calendar", .cyan, "Quarterly planning sync — March 3, 10:00 AM", nil, "1.5 hours ago", true),
        ("archivebox", .gray, "Review and archive completed Document Intelligence project", "0.0%", "2 days ago", false),
        ("newspaper", .orange, "Google DeepMind publishes new multi-agent coordination paper", nil, "1 day ago", false),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Title + search + view toggles
            HStack {
                Text("Activity Feed")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                // Search bar
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textFaint)
                    TextField("Search alerts, insights, news, tasks...", text: $searchText)
                        .font(MacTypography.label)
                        .textFieldStyle(.plain)
                }
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.sm)
                .frame(width: 272)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))

                // View toggles
                HStack(spacing: 2) {
                    Button {} label: {
                        Image(systemName: "square.grid.2x2")
                            .font(.system(size: 14))
                            .foregroundStyle(MacColors.textSecondary)
                            .frame(width: 26, height: 26)
                    }
                    .buttonStyle(.plain)

                    Button {} label: {
                        Image(systemName: "list.bullet")
                            .font(.system(size: 14))
                            .foregroundStyle(MacColors.textSecondary)
                            .frame(width: 26, height: 26)
                    }
                    .buttonStyle(.plain)
                }
            }

            // Filter tabs
            HStack(spacing: 0) {
                ForEach(filters, id: \.self) { filter in
                    Button {
                        withAnimation(.easeInOut(duration: 0.15)) {
                            selectedFilter = filter
                        }
                    } label: {
                        Text(filter)
                            .font(MacTypography.body)
                            .foregroundStyle(
                                selectedFilter == filter
                                    ? MacColors.textPrimary
                                    : MacColors.textSecondary
                            )
                            .padding(.horizontal, MacSpacing.md)
                            .padding(.vertical, MacSpacing.sm)
                            .background(
                                selectedFilter == filter
                                    ? MacColors.activeTabBackground
                                    : Color.clear
                            )
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }

                Spacer()

                Text("12 updates")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
            }

            // Feed items
            VStack(spacing: MacSpacing.sm) {
                ForEach(feedItems.indices, id: \.self) { index in
                    feedItemRow(feedItems[index])
                }
            }
        }
        .padding(MacSpacing.xl)
        .background(MacColors.panelBackground)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    private func feedItemRow(_ item: (icon: String, iconColor: Color, description: String, metric: String?, time: String, hasDot: Bool)) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(item.iconColor.opacity(0.15))
                    .frame(width: MacSize.feedItemIconSize, height: MacSize.feedItemIconSize)
                Image(systemName: item.icon)
                    .font(.system(size: 14))
                    .foregroundStyle(item.iconColor)
            }

            // Status dot
            if item.hasDot {
                Circle()
                    .fill(item.iconColor)
                    .frame(width: MacSize.statusDotSize, height: MacSize.statusDotSize)
            }

            // Description
            Text(item.description)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()

            // Metric
            if let metric = item.metric {
                Text(metric)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.amberAccent)
            }

            // Timestamp
            Text(item.time)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(height: MacSize.feedItemHeight)
        .padding(.horizontal, MacSpacing.xl)
    }
}
