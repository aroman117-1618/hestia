import SwiftUI
import HestiaShared

/// Full-screen article reader for wiki content
struct WikiArticleDetailView: View {
    let article: WikiArticle
    @ObservedObject var viewModel: WikiViewModel

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if article.isGenerated || article.isStatic {
                ScrollView {
                    WikiArticleContentView(article: article)
                        .padding(.bottom, Spacing.xxl)
                }
            } else {
                // Not yet generated
                VStack(spacing: Spacing.lg) {
                    Spacer()

                    Image(systemName: article.moduleIcon)
                        .font(.system(size: 48))
                        .foregroundColor(.white.opacity(0.2))

                    VStack(spacing: Spacing.sm) {
                        Text(article.title)
                            .font(.headline)
                            .foregroundColor(.white.opacity(0.6))

                        Text("This article hasn't been generated yet.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.4))
                    }

                    Button {
                        Task {
                            await viewModel.generateArticle(
                                type: article.articleType,
                                moduleName: article.moduleName
                            )
                        }
                    } label: {
                        HStack(spacing: Spacing.sm) {
                            if viewModel.isGenerating {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.8)
                            } else {
                                Image(systemName: "sparkles")
                            }
                            Text("Generate (~$0.03)")
                        }
                        .font(.subheadline.weight(.semibold))
                        .foregroundColor(.white)
                        .padding(.horizontal, Spacing.lg)
                        .padding(.vertical, Spacing.sm)
                        .background(Color.white.opacity(0.2))
                        .cornerRadius(CornerRadius.small)
                    }
                    .disabled(viewModel.isGenerating)

                    Spacer()
                }
            }
        }
        .navigationTitle(article.title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Preview

struct WikiArticleDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiArticleDetailView(
                article: WikiArticle(
                    id: "module-memory",
                    articleType: "module",
                    title: "Memory Layer",
                    subtitle: "How Hestia remembers",
                    content: "# Memory Layer\n\nThe memory module handles long-term storage...",
                    moduleName: "memory",
                    sourceHash: nil,
                    generationStatus: "complete",
                    generatedAt: "2026-02-27T12:00:00",
                    generationModel: "claude-sonnet",
                    wordCount: 350,
                    estimatedReadTime: 2
                ),
                viewModel: WikiViewModel()
            )
        }
        .preferredColorScheme(.dark)
    }
}
