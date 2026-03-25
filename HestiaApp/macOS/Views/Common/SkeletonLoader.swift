import SwiftUI

// MARK: - Skeleton Shapes

/// Composable skeleton placeholder shapes for loading states.

struct SkeletonLine: View {
    var width: CGFloat? = nil
    var height: CGFloat = 14

    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(MacColors.searchInputBackground)
            .frame(width: width, height: height)
            .shimmer()
    }
}

struct SkeletonRect: View {
    var height: CGFloat = 80
    var cornerRadius: CGFloat = MacCornerRadius.panel

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius)
            .fill(MacColors.searchInputBackground)
            .frame(height: height)
            .shimmer()
    }
}

struct SkeletonCircle: View {
    var size: CGFloat = 40

    var body: some View {
        Circle()
            .fill(MacColors.searchInputBackground)
            .frame(width: size, height: size)
            .shimmer()
    }
}

// MARK: - Prebuilt Skeleton Layouts

/// Card skeleton matching StatCard layout
struct StatCardSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                SkeletonCircle(size: MacSize.statCardIconCircle)
                Spacer()
            }
            SkeletonLine(width: 60, height: 12)
            SkeletonLine(width: 80, height: 22)
        }
        .padding(MacSpacing.xl)
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

/// Feed item skeleton matching feedItemRow layout
struct FeedItemSkeleton: View {
    var body: some View {
        HStack(spacing: MacSpacing.md) {
            SkeletonCircle(size: MacSize.feedItemIconSize)
            SkeletonLine(width: 120, height: 12)
            Spacer()
            SkeletonLine(width: 60, height: 10)
        }
        .frame(height: MacSize.feedItemHeight)
        .padding(.horizontal, MacSpacing.xl)
    }
}

/// Hero section skeleton
struct HeroSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            SkeletonLine(width: 140, height: 12)
            SkeletonLine(width: 260, height: 28)
            SkeletonLine(width: 320, height: 14)
            HStack(spacing: MacSpacing.md) {
                SkeletonRect(height: 36, cornerRadius: MacCornerRadius.search)
                    .frame(width: 120)
                SkeletonRect(height: 36, cornerRadius: MacCornerRadius.search)
                    .frame(width: 120)
            }
        }
        .padding(MacSpacing.xxl)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }
}
