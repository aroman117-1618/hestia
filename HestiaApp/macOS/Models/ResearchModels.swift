import Foundation

// MARK: - Research Graph API Models

struct ResearchGraphResponse: Codable {
    let nodes: [ResearchGraphNode]
    let edges: [ResearchGraphEdge]
    let clusters: [ResearchGraphCluster]
    let nodeCount: Int
    let edgeCount: Int
    let metadata: [String: AnyCodableValue]
}

struct ResearchGraphNode: Codable, Identifiable {
    let id: String
    let content: String
    let nodeType: String
    let category: String
    let label: String
    let confidence: Double
    let weight: Double
    let topics: [String]
    let entities: [String]
    let position: GraphPosition
    let radius: Double
    let color: String
    let lastActive: String?
    let metadata: [String: AnyCodableValue]?
}

struct GraphPosition: Codable {
    let x: Double
    let y: Double
    let z: Double
}

struct ResearchGraphEdge: Codable, Identifiable {
    let id: String
    let fromId: String
    let toId: String
    let edgeType: String
    let weight: Double
    let count: Int
}

struct ResearchGraphCluster: Codable, Identifiable {
    let id: String
    let label: String
    let nodeIds: [String]
    let color: String
}

// MARK: - Principles API Models

struct ResearchPrinciple: Codable, Identifiable {
    let id: String
    let content: String
    let domain: String
    let confidence: Double
    let status: String
    let sourceChunkIds: [String]
    let topics: [String]
    let entities: [String]
    let validationCount: Int
    let contradictionCount: Int
    let createdAt: String?
    let updatedAt: String?

    var isPending: Bool { status == "pending" }
    var isApproved: Bool { status == "approved" }
    var isRejected: Bool { status == "rejected" }
}

struct PrincipleListResponse: Codable {
    let principles: [ResearchPrinciple]
    let total: Int
}

struct DistillResponse: Codable {
    let principles_extracted: Int
    let new: Int
    let input_chunks: Int?
}

struct PrincipleActionResponse: Codable {
    let id: String
    let content: String
    let domain: String
    let confidence: Double
    let status: String
}

struct FactInvalidateResponse: Codable {
    let factId: String
    let status: String
    let invalidAt: String?
    let reason: String?

    private enum CodingKeys: String, CodingKey {
        case factId = "fact_id"
        case status
        case invalidAt = "invalid_at"
        case reason
    }
}
