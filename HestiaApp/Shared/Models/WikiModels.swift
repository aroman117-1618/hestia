import Foundation

// MARK: - Wiki Article Type

enum WikiArticleType: String, Codable, CaseIterable {
    case overview
    case module
    case decision
    case roadmap
    case diagram

    var displayName: String {
        switch self {
        case .overview: return "Overview"
        case .module: return "Modules"
        case .decision: return "Decisions"
        case .roadmap: return "Roadmap"
        case .diagram: return "Diagrams"
        }
    }

    var iconName: String {
        switch self {
        case .overview: return "building.columns"
        case .module: return "puzzlepiece"
        case .decision: return "doc.text"
        case .roadmap: return "flag"
        case .diagram: return "diagram.flow"
        }
    }
}

// MARK: - Wiki Tab Category (Thematic Grouping)

enum WikiTabCategory: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case core = "Core Functionality"
    case skills = "Skills & Automation"
    case memory = "Memory & Learning"
    case resources = "Resources & Tools"

    var id: String { rawValue }

    var iconName: String {
        switch self {
        case .overview: return "building.columns"
        case .core: return "gearshape.2"
        case .skills: return "theatermasks"
        case .memory: return "brain"
        case .resources: return "wrench.and.screwdriver"
        }
    }

    /// Module names belonging to this tab category.
    static func modules(for category: WikiTabCategory) -> [String] {
        switch category {
        case .overview: return []
        case .core: return ["security", "logging", "inference", "cloud", "orchestration", "api"]
        case .skills: return ["execution", "council", "orders", "tasks", "agents", "proactive"]
        case .memory: return ["memory", "voice", "wiki", "user"]
        case .resources: return ["apple", "health", "explorer", "newsfeed", "investigate"]
        }
    }
}

// MARK: - Roadmap Milestone Models

struct WikiRoadmapMilestone: Codable, Identifiable {
    let id: String
    let title: String
    let status: String
    let scope: String

    var statusColor: String {
        switch status.lowercased() {
        case "complete": return "green"
        case "in_progress", "in progress": return "amber"
        default: return "gray"
        }
    }
}

struct WikiRoadmapMilestoneGroup: Codable, Identifiable {
    let id: String
    let title: String
    let order: Int
    let milestones: [WikiRoadmapMilestone]
}

struct WikiRoadmapResponse: Codable {
    let groups: [WikiRoadmapMilestoneGroup]
    let whatsNext: String
}

// MARK: - Wiki Article

struct WikiArticle: Codable, Identifiable {
    let id: String
    let articleType: String
    let title: String
    let subtitle: String
    let content: String
    let moduleName: String?
    let sourceHash: String?
    let generationStatus: String
    let generatedAt: String?
    let generationModel: String?
    let wordCount: Int
    let estimatedReadTime: Int

    var type: WikiArticleType {
        WikiArticleType(rawValue: articleType) ?? .overview
    }

    var isGenerated: Bool {
        generationStatus == "complete"
    }

    var isStatic: Bool {
        generationStatus == "static"
    }

    var isPending: Bool {
        generationStatus == "pending" || generationStatus == "failed"
    }

    var readTimeBadge: String {
        "\(estimatedReadTime) min read"
    }

    /// SF Symbol icon for module articles
    var moduleIcon: String {
        guard let name = moduleName else { return "doc" }
        return WikiModuleIcons.icon(for: name)
    }
}

// MARK: - API Response Models

struct WikiArticleListResponse: Codable {
    let articles: [WikiArticle]
    let count: Int
}

struct WikiGenerateRequest: Codable {
    let articleType: String
    let moduleName: String?
}

struct WikiGenerateResponse: Codable {
    let article: WikiArticle
    let status: String
}

struct WikiGenerateAllResponse: Codable {
    let overview: String?
    let modules: [String: String]
    let diagrams: [String: String]
    let errors: [String]
}

struct WikiRefreshResponse: Codable {
    let decisions: Int
    let roadmap: Int
}

// MARK: - Module Icons

enum WikiModuleIcons {
    static func icon(for moduleName: String) -> String {
        switch moduleName {
        case "security": return "lock.shield"
        case "logging": return "doc.text.magnifyingglass"
        case "inference": return "cpu"
        case "cloud": return "cloud"
        case "council": return "person.3"
        case "memory": return "brain"
        case "orchestration": return "gearshape.2"
        case "execution": return "terminal"
        case "apple": return "apple.logo"
        case "health": return "heart.fill"
        case "tasks": return "checklist"
        case "orders": return "clock.arrow.circlepath"
        case "agents": return "theatermasks"
        case "user": return "person.circle"
        case "proactive": return "sparkles"
        case "voice": return "waveform"
        case "api": return "network"
        case "persona": return "person.text.rectangle"
        case "wiki": return "book"
        case "explorer": return "folder.badge.gearshape"
        case "investigate": return "magnifyingglass"
        case "newsfeed": return "newspaper"
        // Diagram types
        case "architecture": return "building.columns"
        case "request-lifecycle": return "arrow.triangle.capsulepath"
        case "data-flow": return "arrow.left.arrow.right"
        default: return "doc"
        }
    }
}
