import Foundation

// MARK: - Research Canvas Board Persistence

struct ResearchBoard: Codable, Identifiable {
    let id: String
    var name: String
    var layoutJson: String
    let createdAt: String
    var updatedAt: String
}

struct ResearchBoardListResponse: Codable {
    let boards: [ResearchBoard]
}

// MARK: - Canvas Entity (lightweight, for sidebar + detail)

struct ResearchCanvasEntity: Codable, Identifiable {
    let id: String
    let name: String
    let entityType: String
    let connectionCount: Int
    let createdAt: String?
}

struct ResearchCanvasEntityListResponse: Codable {
    let entities: [ResearchCanvasEntity]
    let total: Int
}

// MARK: - Canvas Node Types

enum ResearchCanvasNodeType: String, Codable, CaseIterable {
    case entity
    case fact
    case principle
    case memory
    case annotation
    case group

    var icon: String {
        switch self {
        case .entity: return "person.text.rectangle"
        case .fact: return "link"
        case .principle: return "lightbulb"
        case .memory: return "brain"
        case .annotation: return "note.text"
        case .group: return "rectangle.3.group"
        }
    }

    var label: String {
        switch self {
        case .entity: return "Entity"
        case .fact: return "Fact"
        case .principle: return "Principle"
        case .memory: return "Memory"
        case .annotation: return "Annotation"
        case .group: return "Group"
        }
    }
}

// MARK: - Temporal Fact (for detail pane)

struct ResearchTemporalFact: Codable, Identifiable {
    let id: String
    let subjectId: String
    let objectId: String
    let predicate: String
    let validFrom: String?
    let validTo: String?
    let confidence: Double
    let source: String?
}

struct ResearchTemporalFactListResponse: Codable {
    let facts: [ResearchTemporalFact]
    let total: Int
}

// MARK: - Entity Reference (cross-links from Task 2)

struct ResearchEntityReference: Codable, Identifiable {
    let id: String
    let entityId: String
    let referenceType: String
    let referenceId: String
    let referenceLabel: String?
    let createdAt: String?
}

struct ResearchEntityReferenceListResponse: Codable {
    let references: [ResearchEntityReference]
    let total: Int
}
