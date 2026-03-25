import SwiftUI
import HestiaShared

/// Module list tab — scrollable cards for each Hestia backend module
struct WikiModuleListView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.md) {
                if viewModel.moduleArticles.isEmpty {
                    emptyState
                } else {
                    ForEach(viewModel.moduleArticles) { article in
                        NavigationLink(destination: WikiArticleDetailView(article: article, viewModel: viewModel)) {
                            moduleCard(article)
                        }
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.bottom, Spacing.xxl)
        }
    }

    // MARK: - Module Card

    private func moduleCard(_ article: WikiArticle) -> some View {
        HStack(spacing: Spacing.md) {
            // Module icon
            Image(systemName: article.moduleIcon)
                .font(.system(size: 20))
                .foregroundColor(.textPrimary)
                .frame(width: 40, height: 40)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.small)

            // Title and subtitle
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(article.title)
                        .font(.cardTitle)
                        .foregroundColor(.textPrimary)

                    if article.isPending {
                        Circle()
                            .fill(Color.textTertiary)
                            .frame(width: 6, height: 6)
                    }
                }

                Text(article.subtitle)
                    .font(.caption)
                    .foregroundColor(.textSecondary)
                    .lineLimit(1)
            }

            Spacer()

            // Read time badge
            if article.isGenerated {
                Text(article.readTimeBadge)
                    .font(.caption2)
                    .foregroundColor(.textTertiary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.bgSurface)
                    .cornerRadius(4)
            }

            Image(systemName: "chevron.right")
                .foregroundColor(.textTertiary)
                .font(.caption)
        }
        .settingsRow()
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
                .frame(height: Spacing.xxl)

            Image(systemName: "puzzlepiece")
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            VStack(spacing: Spacing.sm) {
                Text("Module Deep Dives")
                    .font(.headline)
                    .foregroundColor(.textSecondary)

                Text("Generate field guide entries for each of Hestia's 19 backend modules.")
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }

            Button {
                Task {
                    await viewModel.generateAll()
                }
            } label: {
                HStack(spacing: Spacing.sm) {
                    if viewModel.isGenerating {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "sparkles")
                    }
                    Text("Generate All (~$0.80)")
                }
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.textPrimary)
                .padding(.horizontal, Spacing.lg)
                .padding(.vertical, Spacing.sm)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.small)
            }
            .disabled(viewModel.isGenerating)
        }
    }
}

// MARK: - Preview

struct WikiModuleListView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiModuleListView(viewModel: WikiViewModel())
        }
        .preferredColorScheme(.dark)
    }
}
