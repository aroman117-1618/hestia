import SwiftUI
import AppKit
import SceneKit
import HestiaShared

/// macOS ViewModel for the Neural Net 3D graph visualization
///
/// Adapted from the iOS NeuralNetViewModel — uses NSColor for SceneKit materials.
/// Fetches memory chunks via APIClient and computes a force-directed 3D layout.
@MainActor
class MacNeuralNetViewModel: ObservableObject {
    // MARK: - Published State

    @Published var isLoading = false
    @Published var nodes: [GraphNode] = []
    @Published var edges: [GraphEdge] = []
    @Published var selectedNode: GraphNode? {
        didSet { selectedConnectedNodes = connectedNodes(for: selectedNode?.id ?? "") }
    }
    @Published var selectedConnectedNodes: [GraphNode] = []
    @Published var memoryCount: Int = 0

    // MARK: - Types

    struct GraphNode: Identifiable, Equatable {
        let id: String
        let content: String
        let chunkType: ChunkType
        let confidence: Double
        let topics: [String]
        let entities: [String]
        var position: SIMD3<Float> = .zero

        static func == (lhs: GraphNode, rhs: GraphNode) -> Bool {
            lhs.id == rhs.id
        }

        var color: NSColor {
            chunkType.nodeColor
        }

        var swiftUIColor: Color {
            chunkType.swiftUIColor
        }

        var displayName: String {
            chunkType.displayName
        }

        var displayIcon: String {
            chunkType.displayIcon
        }

        var radius: Float {
            Float(0.15 + confidence * 0.15)
        }
    }

    struct GraphEdge: Identifiable {
        let id: String
        let fromId: String
        let toId: String
        let weight: Float

        init(from: String, to: String, weight: Float) {
            self.id = "\(from)-\(to)"
            self.fromId = from
            self.toId = to
            self.weight = weight
        }
    }

    // MARK: - Public Methods

    func loadGraph() async {
        isLoading = true

        do {
            let results = try await APIClient.shared.searchMemory(query: "*", limit: 50)
            memoryCount = results.count

            var graphNodes = results.map { result in
                GraphNode(
                    id: result.chunk.id,
                    content: result.chunk.content,
                    chunkType: result.chunk.chunkType,
                    confidence: result.chunk.metadata.confidence,
                    topics: result.chunk.tags.topics,
                    entities: result.chunk.tags.entities
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
                        graphEdges.append(GraphEdge(from: graphNodes[i].id, to: graphNodes[j].id, weight: weight))
                    }
                }
            }

            computeLayout(nodes: &graphNodes, edges: graphEdges)
            self.nodes = graphNodes
            self.edges = graphEdges

        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Failed to load graph: \(error)")
            #endif
            loadMockGraph()
        }

        isLoading = false
    }

    /// Find all nodes connected to the given node via edges
    func connectedNodes(for nodeId: String) -> [GraphNode] {
        let connectedIds = edges.compactMap { edge -> String? in
            if edge.fromId == nodeId { return edge.toId }
            if edge.toId == nodeId { return edge.fromId }
            return nil
        }
        return connectedIds.compactMap { id in nodes.first(where: { $0.id == id }) }
    }

    // MARK: - Force Simulation

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
                chunkType: result.chunk.chunkType,
                confidence: result.chunk.metadata.confidence,
                topics: result.chunk.tags.topics,
                entities: result.chunk.tags.entities
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
                    graphEdges.append(GraphEdge(from: graphNodes[i].id, to: graphNodes[j].id, weight: weight))
                }
            }
        }

        computeLayout(nodes: &graphNodes, edges: graphEdges)
        self.nodes = graphNodes
        self.edges = graphEdges
    }
}

// MARK: - ChunkType Display Mapping

extension ChunkType {
    /// Human-friendly display name (avoids snake_case rawValue)
    var displayName: String {
        switch self {
        case .conversation: return "Chat Message"
        case .research: return "Research Note"
        case .decision: return "Decision"
        case .actionItem: return "Action Item"
        case .fact: return "Fact"
        case .preference: return "Preference"
        case .system: return "System"
        }
    }

    /// SF Symbol icon for display in detail panel (unique per type)
    var displayIcon: String {
        switch self {
        case .conversation: return "bubble.left"
        case .research: return "note.text"
        case .decision: return "arrow.triangle.branch"
        case .actionItem: return "checklist"
        case .fact: return "book.closed"
        case .preference: return "slider.horizontal.3"
        case .system: return "gear"
        }
    }

    /// NSColor for SceneKit materials
    var nodeColor: NSColor {
        switch self {
        case .preference: return NSColor(red: 0.6, green: 0.3, blue: 0.9, alpha: 1)
        case .fact: return NSColor(red: 0.2, green: 0.5, blue: 1.0, alpha: 1)
        case .decision: return NSColor(red: 1.0, green: 0.6, blue: 0.2, alpha: 1)
        case .actionItem: return NSColor(red: 1.0, green: 0.3, blue: 0.3, alpha: 1)
        case .conversation: return NSColor(red: 0.5, green: 0.5, blue: 0.5, alpha: 1)
        case .research: return NSColor(red: 0.2, green: 0.8, blue: 0.6, alpha: 1)
        case .system: return NSColor(red: 0.4, green: 0.4, blue: 0.4, alpha: 1)
        }
    }

    /// SwiftUI Color for UI elements
    var swiftUIColor: Color {
        switch self {
        case .preference: return Color(red: 0.6, green: 0.3, blue: 0.9)
        case .fact: return Color(red: 0.2, green: 0.5, blue: 1.0)
        case .decision: return Color(red: 1.0, green: 0.6, blue: 0.2)
        case .actionItem: return Color(red: 1.0, green: 0.3, blue: 0.3)
        case .conversation: return Color(red: 0.5, green: 0.5, blue: 0.5)
        case .research: return Color(red: 0.2, green: 0.8, blue: 0.6)
        case .system: return Color(red: 0.4, green: 0.4, blue: 0.4)
        }
    }
}
