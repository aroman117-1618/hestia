import Foundation
import SwiftUI
import HestiaShared

/// ViewModel for the Wiki documentation hub
@MainActor
class WikiViewModel: ObservableObject {

    // MARK: - Tab

    enum Tab: String, CaseIterable, Identifiable {
        case overview = "Overview"
        case modules = "Modules"
        case decisions = "Decisions"
        case roadmap = "Roadmap"
        case diagrams = "Diagrams"

        var id: String { rawValue }

        var iconName: String {
            switch self {
            case .overview: return "building.columns"
            case .modules: return "puzzlepiece"
            case .decisions: return "doc.text"
            case .roadmap: return "flag"
            case .diagrams: return "diagram.flow"
            }
        }
    }

    // MARK: - Published State

    @Published var selectedTab: Tab = .overview
    @Published var articles: [WikiArticle] = []
    @Published var isLoading = false
    @Published var isGenerating = false
    @Published var errorMessage: String?
    @Published var refreshResult: String?

    // MARK: - Computed Properties

    var overviewArticle: WikiArticle? {
        articles.first { $0.articleType == "overview" }
    }

    var moduleArticles: [WikiArticle] {
        articles.filter { $0.articleType == "module" }
            .sorted { $0.title < $1.title }
    }

    var decisionArticles: [WikiArticle] {
        articles.filter { $0.articleType == "decision" }
            .sorted { $0.title < $1.title }
    }

    var roadmapArticle: WikiArticle? {
        articles.first { $0.articleType == "roadmap" }
    }

    var diagramArticles: [WikiArticle] {
        articles.filter { $0.articleType == "diagram" }
    }

    var hasStaticContent: Bool {
        !decisionArticles.isEmpty || roadmapArticle != nil
    }

    var hasGeneratedContent: Bool {
        overviewArticle?.isGenerated == true || !moduleArticles.filter(\.isGenerated).isEmpty
    }

    // MARK: - API Client

    private let client: APIClient

    init(client: APIClient = .shared) {
        self.client = client
    }

    // MARK: - Data Loading

    func loadArticles() async {
        isLoading = true
        errorMessage = nil

        do {
            let response: WikiArticleListResponse = try await client.getWikiArticles()
            articles = response.articles
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to load articles: \(error)")
            #endif
            errorMessage = "Could not load wiki articles"
        }

        isLoading = false
    }

    func refreshStaticContent() async {
        isLoading = true
        errorMessage = nil

        do {
            let result: WikiRefreshResponse = try await client.refreshWikiStatic()
            refreshResult = "Loaded \(result.decisions) decisions, \(result.roadmap) roadmap"

            // Reload articles
            await loadArticles()
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to refresh static: \(error)")
            #endif
            errorMessage = "Could not refresh content from server"
        }

        isLoading = false
    }

    // MARK: - Generation

    func generateArticle(type: String, moduleName: String? = nil) async {
        isGenerating = true
        errorMessage = nil

        do {
            let _: WikiGenerateResponse = try await client.generateWikiArticle(
                type: type,
                moduleName: moduleName
            )

            // Reload to get the cached result
            await loadArticles()
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to generate \(type): \(error)")
            #endif
            errorMessage = "Generation failed. Is cloud LLM enabled?"
        }

        isGenerating = false
    }

    func generateAll() async {
        isGenerating = true
        errorMessage = nil

        do {
            let result: WikiGenerateAllResponse = try await client.generateAllWikiArticles()

            if !result.errors.isEmpty {
                errorMessage = "Generated with \(result.errors.count) errors"
            }

            // Reload
            await loadArticles()
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to generate all: \(error)")
            #endif
            errorMessage = "Full generation failed. Is cloud LLM enabled?"
        }

        isGenerating = false
    }
}
