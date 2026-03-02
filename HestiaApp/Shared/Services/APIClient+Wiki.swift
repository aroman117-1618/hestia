import Foundation
import HestiaShared

private struct WikiEmptyBody: Codable {}

/// Wiki API methods added as local extension to HestiaShared's APIClient.
/// These use local WikiModels types (not in HestiaShared) so they live here.
extension APIClient {
    func getWikiArticles(type: String? = nil) async throws -> WikiArticleListResponse {
        var path = "/wiki/articles"
        if let type = type {
            path += "?type=\(type)"
        }
        return try await get(path)
    }

    func getWikiArticle(id: String) async throws -> WikiArticle {
        return try await get("/wiki/articles/\(id)")
    }

    func generateWikiArticle(type: String, moduleName: String? = nil) async throws -> WikiGenerateResponse {
        let request = WikiGenerateRequest(articleType: type, moduleName: moduleName)
        return try await post("/wiki/generate", body: request, timeout: 300)
    }

    func generateAllWikiArticles() async throws -> WikiGenerateAllResponse {
        return try await post("/wiki/generate-all", body: WikiEmptyBody(), timeout: 600)
    }

    func refreshWikiStatic() async throws -> WikiRefreshResponse {
        return try await post("/wiki/refresh-static", body: WikiEmptyBody())
    }
}
