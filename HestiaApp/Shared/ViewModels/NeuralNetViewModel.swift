import SwiftUI
import HestiaShared
import SceneKit
import Combine

// MARK: - API Response Types (inline for iOS — macOS uses ResearchModels.swift)

private struct IOSGraphResponse: Codable {
    let nodes: [IOSGraphNodeResponse]
    let edges: [IOSGraphEdgeResponse]
    let clusters: [IOSGraphClusterResponse]
    let nodeCount: Int
    let edgeCount: Int
}

private struct IOSGraphNodeResponse: Codable {
    let id: String
    let content: String
    let nodeType: String
    let category: String
    let label: String
    let confidence: Double
    let weight: Double
    let topics: [String]
    let entities: [String]
    let position: IOSGraphPosition
    let radius: Double
    let color: String
    let lastActive: String?
}

private struct IOSGraphPosition: Codable {
    let x: Double
    let y: Double
    let z: Double
}

private struct IOSGraphEdgeResponse: Codable {
    let id: String
    let fromId: String
    let toId: String
    let edgeType: String
    let weight: Double
    let count: Int
}

private struct IOSGraphClusterResponse: Codable {
    let id: String
    let label: String
    let nodeIds: [String]
    let color: String
}

/// ViewModel for the Neural Net 3D graph visualization
///
/// Uses the /v1/research/graph API for server-side layout + edges.
/// Falls back to client-side computation from memory search on error.
@MainActor
class NeuralNetViewModel: ObservableObject {
    // MARK: - Published State

    @Published var isLoading = false
    @Published var nodes: [GraphNode] = []
    @Published var edges: [GraphEdge] = []
    @Published var selectedNode: GraphNode?
    @Published var memoryCount: Int = 0

    // MARK: - Dependencies

    private let client: HestiaClientProtocol

    // MARK: - Types

    /// A node in the 3D graph — supports all 7 knowledge graph types
    struct GraphNode: Identifiable {
        let id: String
        let content: String
        let nodeType: String       // "memory", "topic", "entity", "principle", "community", "episode", "fact"
        let category: String
        let chunkType: ChunkType   // for backward compat with memory-only legend
        let confidence: Double
        let weight: Double
        let topics: [String]
        let entities: [String]
        var position: SIMD3<Float> = .zero
        let colorHex: String

        /// Node color — uses server-provided hex, falls back to chunk type
        var color: UIColor {
            UIColor(hex: colorHex) ?? chunkType.nodeColor
        }

        /// Node radius based on weight (importance-blended)
        var radius: Float {
            Float(0.12 + weight * 0.18)
        }

        /// Display name for detail card
        var displayName: String {
            switch nodeType {
            case "topic":     return "Topic"
            case "entity":    return "Entity"
            case "principle": return "Principle"
            case "community": return "Community"
            case "fact":      return "Fact"
            case "episode":   return "Episode"
            default:          return chunkType.rawValue.capitalized
            }
        }

        /// SF Symbol for detail card
        var displayIcon: String {
            switch nodeType {
            case "topic":     return "tag"
            case "entity":    return "person.text.rectangle"
            case "principle": return "lightbulb"
            case "community": return "person.3"
            case "fact":      return "link"
            case "episode":   return "clock"
            default:
                switch chunkType {
                case .conversation: return "bubble.left"
                case .research:     return "note.text"
                case .decision:     return "arrow.triangle.branch"
                case .actionItem:   return "checklist"
                case .fact:         return "book.closed"
                case .preference:   return "slider.horizontal.3"
                case .system:       return "gear"
                }
            }
        }
    }

    /// An edge connecting two nodes
    struct GraphEdge: Identifiable {
        let id: String
        let fromId: String
        let toId: String
        let weight: Float
        let edgeType: String

        init(from: String, to: String, weight: Float, edgeType: String = "shared_topic") {
            self.id = "\(from)-\(to)"
            self.fromId = from
            self.toId = to
            self.weight = weight
            self.edgeType = edgeType
        }
    }

    // MARK: - Initialization

    init(client: HestiaClientProtocol? = nil) {
        // Default to APIClient.shared for production; pass MockHestiaClient() for previews
        self.client = client ?? APIClient.shared
    }

    // MARK: - Public Methods

    /// Load graph data from the server API, falling back to client-side computation
    func loadGraph() async {
        isLoading = true

        // Try server-side graph first
        do {
            let response: IOSGraphResponse = try await APIClient.shared.get("../v1/research/graph?limit=50&mode=legacy")
            applyServerResponse(response)
        } catch {
            #if DEBUG
            print("[NeuralNetViewModel] Server graph failed: \(error), using client-side fallback")
            #endif
            // Fall back to client-side computation from memory search
            await loadClientSideGraph()
        }

        isLoading = false
    }

    // MARK: - Server Response

    private func applyServerResponse(_ response: IOSGraphResponse) {
        memoryCount = response.nodeCount

        nodes = response.nodes.map { apiNode in
            GraphNode(
                id: apiNode.id,
                content: apiNode.content,
                nodeType: apiNode.nodeType,
                category: apiNode.category,
                chunkType: ChunkType(rawValue: apiNode.category) ?? .conversation,
                confidence: apiNode.confidence,
                weight: apiNode.weight,
                topics: apiNode.topics,
                entities: apiNode.entities,
                position: SIMD3<Float>(
                    Float(apiNode.position.x),
                    Float(apiNode.position.y),
                    Float(apiNode.position.z)
                ),
                colorHex: apiNode.color
            )
        }

        edges = response.edges.map { apiEdge in
            GraphEdge(
                from: apiEdge.fromId,
                to: apiEdge.toId,
                weight: Float(apiEdge.weight),
                edgeType: apiEdge.edgeType
            )
        }
    }

    // MARK: - Client-Side Fallback

    private func loadClientSideGraph() async {
        do {
            let results = try await client.searchMemory(query: "*", limit: 50)
            memoryCount = results.count

            var graphNodes = results.map { result in
                GraphNode(
                    id: result.chunk.id,
                    content: result.chunk.content,
                    nodeType: "memory",
                    category: result.chunk.chunkType.rawValue,
                    chunkType: result.chunk.chunkType,
                    confidence: result.chunk.metadata.confidence,
                    weight: result.relevanceScore,
                    topics: result.chunk.tags.topics,
                    entities: result.chunk.tags.entities,
                    colorHex: result.chunk.chunkType.colorHex
                )
            }

            var graphEdges: [GraphEdge] = []
            for i in 0..<graphNodes.count {
                for j in (i + 1)..<graphNodes.count {
                    let sharedTopics = Set(graphNodes[i].topics).intersection(Set(graphNodes[j].topics))
                    let sharedEntities = Set(graphNodes[i].entities).intersection(Set(graphNodes[j].entities))
                    let sharedCount = sharedTopics.count + sharedEntities.count

                    if sharedCount > 0 {
                        let weight = min(Float(sharedCount) / 3.0, 1.0)
                        graphEdges.append(GraphEdge(
                            from: graphNodes[i].id,
                            to: graphNodes[j].id,
                            weight: weight
                        ))
                    }
                }
            }

            computeLayout(nodes: &graphNodes, edges: graphEdges)
            self.nodes = graphNodes
            self.edges = graphEdges

        } catch {
            #if DEBUG
            print("[NeuralNetViewModel] Client-side graph failed: \(error)")
            #endif
            loadMockGraph()
        }
    }

    // MARK: - Force Simulation Layout

    private func computeLayout(nodes: inout [GraphNode], edges: [GraphEdge]) {
        let count = nodes.count
        guard count > 0 else { return }

        for i in 0..<count {
            let theta = Float.random(in: 0...(2 * .pi))
            let phi = Float.random(in: 0...Float.pi)
            let r: Float = 2.0
            nodes[i].position = SIMD3<Float>(
                r * sin(phi) * cos(theta),
                r * sin(phi) * sin(theta),
                r * cos(phi)
            )
        }

        let nodeIndexMap = Dictionary(uniqueKeysWithValues: nodes.enumerated().map { ($1.id, $0) })
        let edgePairs = edges.compactMap { edge -> (Int, Int, Float)? in
            guard let fromIdx = nodeIndexMap[edge.fromId],
                  let toIdx = nodeIndexMap[edge.toId] else { return nil }
            return (fromIdx, toIdx, edge.weight)
        }

        let iterations = 120
        let centerStrength: Float = 0.01
        let repulsionStrength: Float = 1.5
        let linkStrength: Float = 0.05
        let linkDistance: Float = 2.0
        let damping: Float = 0.9

        var velocities = [SIMD3<Float>](repeating: .zero, count: count)

        for _ in 0..<iterations {
            for i in 0..<count {
                velocities[i] -= nodes[i].position * centerStrength
            }

            for i in 0..<count {
                for j in (i + 1)..<count {
                    var delta = nodes[i].position - nodes[j].position
                    let dist = max(simd_length(delta), 0.1)
                    delta = delta / dist
                    let force = repulsionStrength / (dist * dist)
                    velocities[i] += delta * force
                    velocities[j] -= delta * force
                }
            }

            for (fromIdx, toIdx, weight) in edgePairs {
                guard fromIdx != toIdx else { continue }
                var delta = nodes[toIdx].position - nodes[fromIdx].position
                let dist = max(simd_length(delta), 0.1)
                delta = delta / dist
                let displacement = (dist - linkDistance) * linkStrength * weight
                velocities[fromIdx] += delta * displacement
                velocities[toIdx] -= delta * displacement
            }

            for i in 0..<count {
                velocities[i] *= damping
                nodes[i].position += velocities[i]
            }
        }
    }

    // MARK: - Mock Data Fallback

    private func loadMockGraph() {
        let results = MemorySearchResult.mockResults
        memoryCount = results.count

        var graphNodes = results.map { result in
            GraphNode(
                id: result.chunk.id,
                content: result.chunk.content,
                nodeType: "memory",
                category: result.chunk.chunkType.rawValue,
                chunkType: result.chunk.chunkType,
                confidence: result.chunk.metadata.confidence,
                weight: result.relevanceScore,
                topics: result.chunk.tags.topics,
                entities: result.chunk.tags.entities,
                colorHex: result.chunk.chunkType.colorHex
            )
        }

        var graphEdges: [GraphEdge] = []
        for i in 0..<graphNodes.count {
            for j in (i + 1)..<graphNodes.count {
                let sharedTopics = Set(graphNodes[i].topics).intersection(Set(graphNodes[j].topics))
                let sharedEntities = Set(graphNodes[i].entities).intersection(Set(graphNodes[j].entities))
                let sharedCount = sharedTopics.count + sharedEntities.count

                if sharedCount > 0 {
                    let weight = min(Float(sharedCount) / 3.0, 1.0)
                    graphEdges.append(GraphEdge(
                        from: graphNodes[i].id,
                        to: graphNodes[j].id,
                        weight: weight
                    ))
                }
            }
        }

        computeLayout(nodes: &graphNodes, edges: graphEdges)
        self.nodes = graphNodes
        self.edges = graphEdges
    }
}

// MARK: - UIColor Hex Init

private extension UIColor {
    convenience init?(hex: String) {
        let hexString = hex.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "#", with: "")
        guard hexString.count == 6 else { return nil }

        var rgbValue: UInt64 = 0
        Scanner(string: hexString).scanHexInt64(&rgbValue)

        self.init(
            red: CGFloat((rgbValue & 0xFF0000) >> 16) / 255.0,
            green: CGFloat((rgbValue & 0x00FF00) >> 8) / 255.0,
            blue: CGFloat(rgbValue & 0x0000FF) / 255.0,
            alpha: 1.0
        )
    }
}

// MARK: - ChunkType Color Extensions (iOS)

private extension ChunkType {
    var nodeColor: UIColor {
        switch self {
        case .preference:   return UIColor(red: 0.6, green: 0.3, blue: 0.9, alpha: 1)
        case .fact:         return UIColor(red: 0.2, green: 0.5, blue: 1.0, alpha: 1)
        case .decision:     return UIColor(red: 1.0, green: 0.6, blue: 0.2, alpha: 1)
        case .actionItem:   return UIColor(red: 1.0, green: 0.3, blue: 0.3, alpha: 1)
        case .conversation: return UIColor(red: 0.5, green: 0.5, blue: 0.5, alpha: 1)
        case .research:     return UIColor(red: 0.2, green: 0.8, blue: 0.6, alpha: 1)
        case .system:       return UIColor(red: 0.4, green: 0.4, blue: 0.4, alpha: 1)
        }
    }

    var colorHex: String {
        switch self {
        case .conversation: return "#5AC8FA"
        case .fact:         return "#4CD964"
        case .preference:   return "#FF9500"
        case .decision:     return "#FF3B30"
        case .actionItem:   return "#AF52DE"
        case .research:     return "#007AFF"
        case .system:       return "#8E8E93"
        }
    }
}
