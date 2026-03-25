import SwiftUI
import HestiaShared

/// ADR decision list — browsable cards for architectural decisions
struct WikiDecisionsView: View {
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.md) {
                if viewModel.decisionArticles.isEmpty {
                    emptyState
                } else {
                    ForEach(viewModel.decisionArticles) { article in
                        NavigationLink(destination: WikiArticleDetailView(article: article, viewModel: viewModel)) {
                            decisionCard(article)
                        }
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.bottom, Spacing.xxl)
        }
    }

    // MARK: - Decision Card

    private func decisionCard(_ article: WikiArticle) -> some View {
        HStack(spacing: Spacing.md) {
            // ADR number badge
            Text(adrNumber(from: article.title))
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .foregroundColor(.textPrimary)
                .frame(width: 40, height: 40)
                .background(Color.bgOverlay)
                .cornerRadius(CornerRadius.small)

            // Title and status
            VStack(alignment: .leading, spacing: 2) {
                Text(adrTitle(from: article.title))
                    .font(.cardTitle)
                    .foregroundColor(.textPrimary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                Text(article.subtitle)
                    .font(.caption)
                    .foregroundColor(statusColor(article.subtitle))
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.textTertiary)
                .font(.caption)
        }
        .settingsRow()
    }

    // MARK: - Helpers

    private func adrNumber(from title: String) -> String {
        // Extract "001" from "ADR-001: Title"
        if let range = title.range(of: #"ADR-(\d+)"#, options: .regularExpression) {
            return String(title[range])
                .replacingOccurrences(of: "ADR-", with: "")
        }
        return "?"
    }

    private func adrTitle(from title: String) -> String {
        // Extract "Title" from "ADR-001: Title"
        if let colonRange = title.range(of: ": ") {
            return String(title[colonRange.upperBound...])
        }
        return title
    }

    private func statusColor(_ status: String) -> Color {
        let lower = status.lowercased()
        if lower.contains("deprecated") {
            return .errorRed
        } else if lower.contains("superseded") {
            return .warningYellow
        }
        return .healthyGreen
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()
                .frame(height: Spacing.xxl)

            Image(systemName: "doc.text")
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            VStack(spacing: Spacing.sm) {
                Text("Architectural Decisions")
                    .font(.headline)
                    .foregroundColor(.textSecondary)

                Text("Tap the refresh button to load ADRs from the decision log.")
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }
        }
    }
}

// MARK: - Preview

struct WikiDecisionsView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiDecisionsView(viewModel: WikiViewModel())
        }
        .preferredColorScheme(.dark)
    }
}
