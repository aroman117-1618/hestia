import SwiftUI
import HestiaShared
import SceneKit
import Combine

/// ViewModel for the Neural Net 3D graph visualization
///
/// Uses a custom force-directed simulation to compute node positions in 3D space,
/// then publishes node/edge data for SceneKit rendering.
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

    /// A node in the 3D graph representing a memory chunk
    struct GraphNode: Identifiable {
        let id: String
        let content: String
        let chunkType: ChunkType
        let confidence: Double
        let topics: [String]
        let entities: [String]
        var position: SIMD3<Float> = .zero

        /// Node color based on chunk type
        var color: UIColor {
            switch chunkType {
            case .preference: return UIColor(red: 0.6, green: 0.3, blue: 0.9, alpha: 1) // Purple
            case .fact: return UIColor(red: 0.2, green: 0.5, blue: 1.0, alpha: 1)        // Blue
            case .decision: return UIColor(red: 1.0, green: 0.6, blue: 0.2, alpha: 1)    // Orange
            case .actionItem: return UIColor(red: 1.0, green: 0.3, blue: 0.3, alpha: 1)  // Red
            case .conversation: return UIColor(red: 0.5, green: 0.5, blue: 0.5, alpha: 1) // Gray
            case .research: return UIColor(red: 0.2, green: 0.8, blue: 0.6, alpha: 1)    // Teal
            case .system: return UIColor(red: 0.4, green: 0.4, blue: 0.4, alpha: 1)      // Dark Gray
            }
        }

        /// Node radius based on confidence (higher confidence = larger node)
        var radius: Float {
            Float(0.15 + confidence * 0.15) // Range: 0.15 - 0.30
        }
    }

    /// An edge connecting two nodes (shared tags create connections)
    struct GraphEdge: Identifiable {
        let id: String
        let fromId: String
        let toId: String
        let weight: Float // 0.0 - 1.0 based on shared tag count

        init(from: String, to: String, weight: Float) {
            self.id = "\(from)-\(to)"
            self.fromId = from
            self.toId = to
            self.weight = weight
        }
    }

    // MARK: - Initialization

    init(client: HestiaClientProtocol? = nil) {
        // Default to APIClient.shared for production; pass MockHestiaClient() for previews
        self.client = client ?? APIClient.shared
    }

    // MARK: - Public Methods

    /// Load memory data and compute graph layout
    func loadGraph() async {
        isLoading = true

        do {
            // Fetch memory chunks — use a broad query to get diverse results
            let results = try await client.searchMemory(query: "*", limit: 50)
            memoryCount = results.count

            // Build nodes from search results
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

            // Build edges from shared topics/entities
            var graphEdges: [GraphEdge] = []
            for i in 0..<graphNodes.count {
                for j in (i + 1)..<graphNodes.count {
                    let sharedTopics = Set(graphNodes[i].topics).intersection(Set(graphNodes[j].topics))
                    let sharedEntities = Set(graphNodes[i].entities).intersection(Set(graphNodes[j].entities))
                    let sharedCount = sharedTopics.count + sharedEntities.count

                    if sharedCount > 0 {
                        let weight = min(Float(sharedCount) / 3.0, 1.0) // Normalize to 0-1
                        graphEdges.append(GraphEdge(
                            from: graphNodes[i].id,
                            to: graphNodes[j].id,
                            weight: weight
                        ))
                    }
                }
            }

            // Compute 3D layout using force simulation
            computeLayout(nodes: &graphNodes, edges: graphEdges)

            self.nodes = graphNodes
            self.edges = graphEdges

        } catch {
            #if DEBUG
            print("[NeuralNetViewModel] Failed to load graph: \(error)")
            #endif
            // Fall back to mock data on error
            loadMockGraph()
        }

        isLoading = false
    }

    // MARK: - Force Simulation Layout

    /// Compute 3D positions using a simple force-directed algorithm
    /// Uses center attraction + node repulsion + edge springs
    private func computeLayout(nodes: inout [GraphNode], edges: [GraphEdge]) {
        let count = nodes.count
        guard count > 0 else { return }

        // Initialize random positions in a sphere
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

        // Build edge lookup using dictionary for O(1) index access
        let nodeIndexMap = Dictionary(uniqueKeysWithValues: nodes.enumerated().map { ($1.id, $0) })
        let edgePairs = edges.compactMap { edge -> (Int, Int, Float)? in
            guard let fromIdx = nodeIndexMap[edge.fromId],
                  let toIdx = nodeIndexMap[edge.toId] else { return nil }
            return (fromIdx, toIdx, edge.weight)
        }

        // Run simulation iterations
        let iterations = 120
        let centerStrength: Float = 0.01
        let repulsionStrength: Float = 1.5
        let linkStrength: Float = 0.05
        let linkDistance: Float = 2.0
        let damping: Float = 0.9

        var velocities = [SIMD3<Float>](repeating: .zero, count: count)

        for _ in 0..<iterations {
            // Center force — pull all nodes toward origin
            for i in 0..<count {
                velocities[i] -= nodes[i].position * centerStrength
            }

            // Repulsion force — nodes push each other away (inverse square)
            for i in 0..<count {
                for j in (i + 1)..<count {
                    var delta = nodes[i].position - nodes[j].position
                    let dist = max(simd_length(delta), 0.1)
                    delta = delta / dist // Normalize
                    let force = repulsionStrength / (dist * dist)
                    velocities[i] += delta * force
                    velocities[j] -= delta * force
                }
            }

            // Link force — connected nodes attract toward linkDistance
            for (fromIdx, toIdx, weight) in edgePairs {
                guard fromIdx != toIdx else { continue }
                var delta = nodes[toIdx].position - nodes[fromIdx].position
                let dist = max(simd_length(delta), 0.1)
                delta = delta / dist // Normalize
                let displacement = (dist - linkDistance) * linkStrength * weight
                velocities[fromIdx] += delta * displacement
                velocities[toIdx] -= delta * displacement
            }

            // Apply velocities with damping
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
