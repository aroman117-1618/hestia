import SwiftUI
import HestiaShared

/// List of recent URL investigations with analysis summaries.
struct InvestigationsListView: View {
    let investigations: [Investigation]

    var body: some View {
        if investigations.isEmpty {
            emptyState
        } else {
            ScrollView {
                LazyVStack(spacing: MacSpacing.sm) {
                    ForEach(investigations, id: \.id) { investigation in
                        investigationCard(investigation)
                    }
                }
                .padding(.top, MacSpacing.sm)
                .padding(.horizontal, MacSpacing.sm)
            }
        }
    }

    // MARK: - Investigation Card

    private func investigationCard(_ item: Investigation) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header: type badge + title
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: item.type.iconName)
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.amberAccent)

                Text(item.type.displayName.uppercased())
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(MacColors.amberAccent.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                Spacer()

                // Status
                statusBadge(item)
            }

            // Title
            Text(item.displayTitle)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(2)

            // URL
            Text(item.url)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.amberAccent.opacity(0.7))
                .lineLimit(1)

            // Analysis snippet
            if item.isComplete && !item.analysis.isEmpty {
                Text(item.analysis)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(3)
            }

            // Key points preview
            if !item.keyPoints.isEmpty {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "list.bullet")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                    Text("\(item.keyPoints.count) key points")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)

                    Spacer()

                    Text(item.createdAt.prefix(10))
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
        }
        .padding(MacSpacing.lg)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Status Badge

    private func statusBadge(_ item: Investigation) -> some View {
        let (text, color): (String, Color) = {
            switch item.statusEnum {
            case .complete: return ("Complete", MacColors.healthGreen)
            case .failed: return ("Failed", MacColors.healthRed)
            case .analyzing: return ("Analyzing", MacColors.healthAmber)
            case .extracting: return ("Extracting", MacColors.healthAmber)
            case .pending: return ("Pending", MacColors.textSecondary)
            }
        }()

        return Text(text)
            .font(MacTypography.metadata)
            .foregroundStyle(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15))
            .clipShape(Capsule())
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "magnifyingglass.circle")
                .font(MacTypography.heroHeading)
                .foregroundStyle(MacColors.textSecondary.opacity(0.3))
            Text("No investigations yet")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Text("Use /investigate in chat to analyze URLs")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, MacSpacing.xxl)
    }
}
