import Foundation

// MARK: - Enums

enum InvestigationContentType: String, Codable, CaseIterable {
    case webArticle = "web_article"
    case youtube
    case tiktok
    case audio
    case video
    case unknown

    var displayName: String {
        switch self {
        case .webArticle: return "Article"
        case .youtube: return "YouTube"
        case .tiktok: return "TikTok"
        case .audio: return "Audio"
        case .video: return "Video"
        case .unknown: return "Unknown"
        }
    }

    var iconName: String {
        switch self {
        case .webArticle: return "doc.text"
        case .youtube: return "play.rectangle"
        case .tiktok: return "music.note"
        case .audio: return "waveform"
        case .video: return "film"
        case .unknown: return "questionmark.circle"
        }
    }
}

enum InvestigationDepth: String, Codable, CaseIterable {
    case quick
    case standard
    case deep

    var displayName: String {
        switch self {
        case .quick: return "Quick"
        case .standard: return "Standard"
        case .deep: return "Deep"
        }
    }
}

enum InvestigationStatus: String, Codable {
    case pending
    case extracting
    case analyzing
    case complete
    case failed
}

// MARK: - Models

struct Investigation: Codable, Identifiable {
    let id: String
    let url: String
    let contentType: String
    let depth: String
    let status: String
    let title: String?
    let sourceAuthor: String?
    let sourceDate: String?
    let analysis: String
    let keyPoints: [String]
    let modelUsed: String?
    let tokensUsed: Int
    let wordCount: Int
    let createdAt: String
    let completedAt: String?
    let error: String?

    var type: InvestigationContentType {
        InvestigationContentType(rawValue: contentType) ?? .unknown
    }

    var depthLevel: InvestigationDepth {
        InvestigationDepth(rawValue: depth) ?? .standard
    }

    var statusEnum: InvestigationStatus {
        InvestigationStatus(rawValue: status) ?? .pending
    }

    var isComplete: Bool {
        status == "complete"
    }

    var isFailed: Bool {
        status == "failed"
    }

    var displayTitle: String {
        title ?? url
    }
}

// MARK: - API Request/Response Models

struct InvestigateURLRequest: Codable {
    let url: String
    let depth: String

    init(url: String, depth: InvestigationDepth = .standard) {
        self.url = url
        self.depth = depth.rawValue
    }
}

struct InvestigateCompareRequest: Codable {
    let urls: [String]
    let focus: String?

    init(urls: [String], focus: String? = nil) {
        self.urls = urls
        self.focus = focus
    }
}

struct InvestigationListResponse: Codable {
    let investigations: [Investigation]
    let count: Int
    let total: Int
}

struct ComparisonResponse: Codable {
    let investigations: [Investigation]
    let comparison: String
    let urlsCompared: Int
    let urlsFailed: Int
    let error: String?
}

struct InvestigationDeleteResponse: Codable {
    let deleted: Bool
    let id: String
}
