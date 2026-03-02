import Foundation
import SwiftUI
import HestiaShared

@MainActor
class WikiViewModel: ObservableObject {

    // MARK: - Published State

    @Published var selectedTab: WikiTabCategory = .overview {
        didSet {
            selectedArticleId = nil
            showingRoadmap = false
        }
    }
    @Published var selectedArticleId: String?
    @Published var showingRoadmap = false
    @Published var articles: [WikiArticle] = []
    @Published var isLoading = false
    @Published var isGenerating = false
    @Published var errorMessage: String?
    @Published var refreshResult: String?

    // Roadmap state (Phase 3)
    @Published var roadmapGroups: [WikiRoadmapMilestoneGroup] = []
    @Published var roadmapWhatsNext: String = ""

    // MARK: - Computed Properties

    var overviewArticle: WikiArticle? {
        articles.first { $0.articleType == "overview" }
    }

    var moduleArticles: [WikiArticle] {
        articles.filter { $0.articleType == "module" }
    }

    var selectedArticle: WikiArticle? {
        guard let id = selectedArticleId else { return nil }
        return articles.first { $0.id == id }
    }

    /// Articles for the currently selected tab, sorted to match declared module order.
    var currentTabArticles: [WikiArticle] {
        switch selectedTab {
        case .overview:
            return overviewArticle.map { [$0] } ?? []
        case .core, .skills, .memory, .resources:
            let moduleOrder = WikiTabCategory.modules(for: selectedTab)
            return moduleOrder.compactMap { moduleName in
                moduleArticles.first { $0.moduleName == moduleName }
            }
        }
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
            async let articlesTask: WikiArticleListResponse = client.getWikiArticles()
            async let roadmapTask: Void = loadRoadmap()

            let response = try await articlesTask
            _ = await roadmapTask

            articles = response.articles
            autoSelectBestTab()
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to load articles: \(error)")
            #endif
            errorMessage = "Could not load wiki articles"
        }

        isLoading = false
    }

    func loadRoadmap() async {
        do {
            let response: WikiRoadmapResponse = try await client.getWikiRoadmap()
            roadmapGroups = response.groups
            roadmapWhatsNext = response.whatsNext
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to load roadmap: \(error)")
            #endif
            // Non-fatal — roadmap is optional
        }
    }

    /// Auto-select the first tab that has content, if the current tab is empty.
    private func autoSelectBestTab() {
        let currentHasContent = !currentTabArticles.isEmpty
        guard !currentHasContent else { return }

        let priority: [WikiTabCategory] = [.overview, .core, .skills, .memory, .resources]
        for tab in priority {
            let tabModules = WikiTabCategory.modules(for: tab)
            let hasContent: Bool
            if tab == .overview {
                hasContent = overviewArticle != nil
            } else {
                hasContent = moduleArticles.contains { article in
                    tabModules.contains(article.moduleName ?? "")
                }
            }
            if hasContent {
                selectedTab = tab
                return
            }
        }
    }

    func selectArticle(_ article: WikiArticle) {
        showingRoadmap = false
        selectedArticleId = article.id
    }

    func refreshStaticContent() async {
        isLoading = true
        errorMessage = nil

        do {
            let result: WikiRefreshResponse = try await client.refreshWikiStatic()
            refreshResult = "Loaded \(result.decisions) decisions, \(result.roadmap) roadmap"
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
            let response: WikiGenerateResponse = try await client.generateWikiArticle(
                type: type,
                moduleName: moduleName
            )
            await loadArticles()

            if response.status == "failed" {
                errorMessage = "Generation failed — check your cloud LLM API key in Resources > LLMs (\u{2318}6)"
            }
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to generate \(type): \(error)")
            #endif
            errorMessage = "Could not reach server for generation"
        }

        isGenerating = false
    }

    func generateAll() async {
        isGenerating = true
        errorMessage = nil

        do {
            let result: WikiGenerateAllResponse = try await client.generateAllWikiArticles()
            await loadArticles()

            let moduleResults = result.modules.values
            let diagramResults = result.diagrams.values
            let failedCount = moduleResults.filter { $0 == "failed" }.count
                + diagramResults.filter { $0 == "failed" }.count
                + (result.overview == "failed" ? 1 : 0)

            if failedCount > 0 {
                let total = moduleResults.count + diagramResults.count + 1
                let successCount = total - failedCount
                errorMessage = "\(successCount)/\(total) generated. \(failedCount) failed — check your API key in Resources > LLMs (\u{2318}6)"
            }
        } catch {
            #if DEBUG
            print("[WikiVM] Failed to generate all: \(error)")
            #endif
            errorMessage = "Could not reach server for generation"
        }

        isGenerating = false
    }
}
