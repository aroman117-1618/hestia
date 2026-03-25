import SwiftUI
import HestiaShared

struct ActivityFeed: View {
    let orders: [OrderResponse]
    let newsfeedItems: [NewsfeedItem]
    @Environment(\.layoutMode) private var layoutMode
    @State private var selectedFilter: String = "All Updates"
    @State private var searchText: String = ""

    private let filters = ["All Updates", "Orders", "Memory", "Tasks", "Health", "System"]

    private var filteredItems: [NewsfeedItem] {
        var items = newsfeedItems
        if selectedFilter != "All Updates" {
            let typeMap: [String: String] = [
                "Orders": "order_execution",
                "Memory": "memory_review",
                "Tasks": "task_update",
                "Health": "health_insight",
                "System": "system_alert"
            ]
            if let typeValue = typeMap[selectedFilter] {
                items = items.filter { $0.itemType == typeValue }
            }
        }
        if !searchText.isEmpty {
            items = items.filter {
                $0.title.localizedCaseInsensitiveContains(searchText) ||
                ($0.body ?? "").localizedCaseInsensitiveContains(searchText)
            }
        }
        return items
    }

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Title + search + view toggles
            HStack {
                Text("Activity Feed")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                // Search bar — compact: icon-only, wide: full text field
                if layoutMode.isCompact {
                    Button {} label: {
                        Image(systemName: "magnifyingglass")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textFaint)
                            .frame(width: 32, height: 31.5)
                            .background(MacColors.searchInputBackground)
                            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.hestia)
                    .accessibilityLabel("Search activity")
                    .hoverCursor(.pointingHand)
                } else {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "magnifyingglass")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textFaint)
                        TextField("Search activity...", text: $searchText)
                            .font(MacTypography.label)
                            .textFieldStyle(.plain)
                            .accessibilityLabel("Search activity")
                    }
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.sm)
                    .frame(minWidth: 180, maxWidth: 300)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
            }

            // Filter tabs — scrollable when compact
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 0) {
                    ForEach(filters, id: \.self) { filter in
                        Button {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                selectedFilter = filter
                            }
                        } label: {
                            Text(layoutMode.isCompact ? filterShortLabel(filter) : filter)
                                .font(MacTypography.body)
                                .foregroundStyle(
                                    selectedFilter == filter
                                        ? MacColors.textPrimary
                                        : MacColors.textSecondary
                                )
                                .padding(.horizontal, layoutMode.isCompact ? MacSpacing.sm : MacSpacing.md)
                                .padding(.vertical, MacSpacing.sm)
                                .background(
                                    selectedFilter == filter
                                        ? MacColors.activeTabBackground
                                        : Color.clear
                                )
                                .clipShape(Capsule())
                                .fixedSize()
                        }
                        .buttonStyle(.hestia)
                        .hoverCursor(.pointingHand)
                    }

                    Spacer(minLength: MacSpacing.sm)

                    Text("\(filteredItems.count)")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            // Feed items
            if filteredItems.isEmpty {
                emptyState
            } else {
                VStack(spacing: MacSpacing.sm) {
                    ForEach(filteredItems) { item in
                        feedItemRow(item)
                    }
                }
            }
        }
        .padding(MacSpacing.xl)
        .hestiaPanel()
    }

    private func filterShortLabel(_ filter: String) -> String {
        switch filter {
        case "All Updates": return "All"
        default: return filter
        }
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "tray")
                .font(MacTypography.heroHeading)
                .foregroundStyle(MacColors.textFaint)
            Text("No activity yet")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, MacSpacing.xl)
    }

    private func feedItemRow(_ item: NewsfeedItem) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(item.displayColor.opacity(0.15))
                    .frame(width: MacSize.feedItemIconSize, height: MacSize.feedItemIconSize)
                Image(systemName: item.displayIcon)
                    .font(MacTypography.body)
                    .foregroundStyle(item.displayColor)
            }

            // Unread dot
            if !item.isRead {
                Circle()
                    .fill(MacColors.unreadDot)
                    .frame(width: MacSize.statusDotSize, height: MacSize.statusDotSize)
            }

            // Title
            Text(item.title)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()

            // Body preview
            if let body = item.body, !body.isEmpty {
                Text(body)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(1)
                    .frame(maxWidth: 200, alignment: .trailing)
            }

            // Timestamp
            Text(item.relativeTime)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(height: MacSize.feedItemHeight)
        .padding(.horizontal, MacSpacing.xl)
    }
}
