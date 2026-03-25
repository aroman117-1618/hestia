import SwiftUI
import HestiaShared

struct MacWikiArticleRow: View {
    let article: WikiArticle
    let isSelected: Bool
    @State private var isHovered = false

    var body: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: article.type == .module ? article.moduleIcon : article.type.iconName)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.amberAccent.opacity(0.7))
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(article.title)
                    .font(MacTypography.smallMedium)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                HStack(spacing: MacSpacing.xs) {
                    Text(article.readTimeBadge)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)

                    Circle()
                        .fill(article.isGenerated ? MacColors.healthGreen :
                              article.isStatic ? MacColors.amberAccent :
                              MacColors.healthRed.opacity(0.6))
                        .frame(width: 5, height: 5)
                }
            }

            Spacer()
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, 6)
        .background(
            isSelected ? MacColors.activeTabBackground :
            isHovered ? MacColors.activeNavBackground.opacity(0.5) :
            Color.clear
        )
        .cornerRadius(MacCornerRadius.treeItem)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
    }
}
