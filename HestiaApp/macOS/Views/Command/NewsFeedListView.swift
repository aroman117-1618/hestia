import SwiftUI
import HestiaShared

/// macOS-specific news feed list using MacColors/MacSpacing tokens.
/// Wraps the same data as Shared/NewsfeedTimeline but with macOS design system.
struct NewsFeedListView: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    /// News items filtered for External tab — excludes health insights (belong in Internal)
    private var externalNewsItems: [NewsfeedItem] {
        viewModel.newsfeedItems.filter { $0.source != "health" }
    }

    var body: some View {
        if externalNewsItems.isEmpty {
            emptyState
        } else {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(externalNewsItems) { item in
                        newsfeedRow(item)

                        if item.id != externalNewsItems.last?.id {
                            MacColors.divider
                                .frame(height: 1)
                                .padding(.leading, 52)
                        }
                    }
                }
                .padding(.top, MacSpacing.sm)
            }
        }
    }

    // MARK: - Row

    private func newsfeedRow(_ item: NewsfeedItem) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(item.displayColor.opacity(0.15))
                    .frame(width: MacSize.feedItemIconSize, height: MacSize.feedItemIconSize)
                Image(systemName: item.displayIcon)
                    .font(.system(size: 14))
                    .foregroundStyle(item.displayColor)
            }

            // Unread dot
            if !item.isRead {
                Circle()
                    .fill(MacColors.unreadDot)
                    .frame(width: MacSize.statusDotSize, height: MacSize.statusDotSize)
            }

            // Content
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                if let body = item.body, !body.isEmpty {
                    Text(body)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            // Timestamp
            Text(item.relativeTime)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.horizontal, MacSpacing.lg)
        .frame(height: MacSize.feedItemHeight)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "newspaper")
                .font(.system(size: 28))
                .foregroundStyle(MacColors.textSecondary.opacity(0.3))
            Text("No news items")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Text("Your timeline will populate as Hestia works")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, MacSpacing.xxl)
    }
}
