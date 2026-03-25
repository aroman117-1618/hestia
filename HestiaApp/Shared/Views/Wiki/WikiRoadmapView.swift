import SwiftUI
import HestiaShared

/// Roadmap tab — development timeline and milestones
struct WikiRoadmapView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.lg) {
                if let article = viewModel.roadmapArticle {
                    WikiArticleContentView(article: article)
                } else {
                    emptyState
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.bottom, Spacing.xxl)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
                .frame(height: Spacing.xxl)

            Image(systemName: "flag")
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            VStack(spacing: Spacing.sm) {
                Text("Development Roadmap")
                    .font(.headline)
                    .foregroundColor(.textSecondary)

                Text("Tap the refresh button to load the development plan from the server.")
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }
        }
    }
}

// MARK: - Preview

struct WikiRoadmapView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiRoadmapView(viewModel: WikiViewModel())
        }
        .preferredColorScheme(.dark)
    }
}
