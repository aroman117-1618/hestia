import Foundation

struct PromptVariation: Codable, Identifiable {
    var id: String { label }
    let label: String
    let prompt: String
    let explanation: String
    let modelSuitability: String

    /// Human-readable suitability badge text
    var suitabilityBadge: String {
        switch modelSuitability {
        case "cloud_optimized": return "Cloud-optimized"
        case "local_friendly": return "Local-friendly"
        default: return "Universal"
        }
    }
}

struct RefinePromptRequest: Codable {
    let prompt: String
    let inferenceRoute: String

    enum CodingKeys: String, CodingKey {
        case prompt
        case inferenceRoute = "inference_route"
    }
}

struct RefinePromptResponse: Codable {
    let variations: [PromptVariation]
    let contextUsed: [String]

    enum CodingKeys: String, CodingKey {
        case variations
        case contextUsed = "context_used"
    }
}
