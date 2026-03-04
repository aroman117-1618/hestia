import SwiftUI
import AppKit
import SceneKit
import HestiaShared

/// macOS ViewModel for the Neural Net 3D graph visualization
///
/// Fetches graph data from /v1/research/graph (server-side layout + edges).
/// Falls back to mock data when server is unavailable.
@MainActor
class MacNeuralNetViewModel: ObservableObject {
    // MARK: - Published State (Graph)

    @Published var isLoading = false
    @Published var nodes: [GraphNode] = []
    @Published var edges: [GraphEdge] = []
    @Published var clusters: [GraphCluster] = []
    @Published var selectedNode: GraphNode? {
        didSet { selectedConnectedNodes = connectedNodes(for: selectedNode?.id ?? "") }
    }
    @Published var selectedConnectedNodes: [GraphNode] = []
    @Published var memoryCount: Int = 0

    // MARK: - Published State (Filters)

    @Published var nodeTypeFilter: Set<String> = ["memory", "topic", "entity"]
    @Published var focusTopic: String = ""
    @Published var depthLimit: Int = 3

    // MARK: - Published State (Principles)

    @Published var principles: [ResearchPrinciple] = []
    @Published var isLoadingPrinciples = false
    @Published var isDistilling = false
    @Published var principlesTotal: Int = 0

    // MARK: - Types

    struct GraphNode: Identifiable, Equatable {
        let id: String
        let content: String
        let nodeType: String       // "memory", "topic", "entity", "principle"
        let category: String       // maps to ChunkType for memory nodes
        let label: String
        let confidence: Double
        let weight: Double
        let topics: [String]
        let entities: [String]
        var position: SIMD3<Float> = .zero
        let colorHex: String

        static func == (lhs: GraphNode, rhs: GraphNode) -> Bool {
            lhs.id == rhs.id
        }

        var color: NSColor {
            NSColor(hex: colorHex) ?? .gray
        }

        var swiftUIColor: Color {
            Color(nsColor: color)
        }

        var displayName: String {
            switch nodeType {
            case "topic": return "Topic"
            case "entity": return "Entity"
            case "principle": return "Principle"
            default: return ChunkType(rawValue: category)?.displayName ?? category.capitalized
            }
        }

        var displayIcon: String {
            switch nodeType {
            case "topic": return "tag"
            case "entity": return "person.text.rectangle"
            case "principle": return "lightbulb"
            default: return ChunkType(rawValue: category)?.displayIcon ?? "circle"
            }
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

    struct GraphCluster: Identifiable {
        let id: String
        let label: String
        let nodeIds: [String]
        let color: Color
    }

    // MARK: - Graph Loading

    func loadGraph() async {
        isLoading = true
        defer { isLoading = false }

        // Try cached data first for instant display
        if let cached = CacheManager.shared.get(ResearchGraphResponse.self, forKey: CacheKey.researchGraph) {
            applyGraphResponse(cached)
        }

        // Fetch from server
        do {
            let nodeTypesParam = nodeTypeFilter.isEmpty ? nil : nodeTypeFilter.sorted().joined(separator: ",")
            let topicParam = focusTopic.isEmpty ? nil : focusTopic

            let response = try await APIClient.shared.getResearchGraph(
                limit: 200,
                nodeTypes: nodeTypesParam,
                centerTopic: topicParam
            )
            applyGraphResponse(response)
            CacheManager.shared.cache(response, forKey: CacheKey.researchGraph, ttl: 300)

        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Server graph failed: \(error), using mock")
            #endif
            if nodes.isEmpty {
                loadMockGraph()
            }
        }
    }

    private func applyGraphResponse(_ response: ResearchGraphResponse) {
        memoryCount = response.nodeCount

        nodes = response.nodes.map { apiNode in
            GraphNode(
                id: apiNode.id,
                content: apiNode.content,
                nodeType: apiNode.nodeType,
                category: apiNode.category,
                label: apiNode.label,
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
            GraphEdge(from: apiEdge.fromId, to: apiEdge.toId, weight: Float(apiEdge.weight))
        }

        clusters = response.clusters.map { apiCluster in
            GraphCluster(
                id: apiCluster.id,
                label: apiCluster.label,
                nodeIds: apiCluster.nodeIds,
                color: Color(hex: apiCluster.color)
            )
        }
    }

    // MARK: - Filtered Access

    var filteredNodes: [GraphNode] {
        guard !focusTopic.isEmpty else { return nodes }
        let lower = focusTopic.lowercased()
        return nodes.filter { node in
            node.topics.contains(where: { $0.lowercased().contains(lower) })
            || node.label.lowercased().contains(lower)
            || node.content.lowercased().contains(lower)
        }
    }

    var filteredEdges: [GraphEdge] {
        let validIds = Set(filteredNodes.map(\.id))
        return edges.filter { validIds.contains($0.fromId) && validIds.contains($0.toId) }
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

    // MARK: - Principles

    func loadPrinciples(status: String? = nil) async {
        isLoadingPrinciples = true
        defer { isLoadingPrinciples = false }

        // Cached first
        if let cached = CacheManager.shared.get(PrincipleListResponse.self, forKey: CacheKey.researchPrinciples) {
            principles = cached.principles
            principlesTotal = cached.total
        }

        do {
            let response = try await APIClient.shared.getPrinciples(status: status)
            principles = response.principles
            principlesTotal = response.total
            CacheManager.shared.cache(response, forKey: CacheKey.researchPrinciples, ttl: 120)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Failed to load principles: \(error)")
            #endif
        }
    }

    func distillPrinciples() async {
        isDistilling = true
        defer { isDistilling = false }

        do {
            let result = try await APIClient.shared.distillPrinciples()
            #if DEBUG
            print("[MacNeuralNetViewModel] Distilled \(result.principles_extracted) principles")
            #endif
            // Reload principles to show new ones
            await loadPrinciples()
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Distillation failed: \(error)")
            #endif
        }
    }

    func approvePrinciple(_ id: String) async {
        do {
            _ = try await APIClient.shared.approvePrinciple(id)
            // Update local state
            if let idx = principles.firstIndex(where: { $0.id == id }) {
                await loadPrinciples()
            }
            CacheManager.shared.invalidate(forKey: CacheKey.researchPrinciples)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Approve failed: \(error)")
            #endif
        }
    }

    func rejectPrinciple(_ id: String) async {
        do {
            _ = try await APIClient.shared.rejectPrinciple(id)
            if let idx = principles.firstIndex(where: { $0.id == id }) {
                await loadPrinciples()
            }
            CacheManager.shared.invalidate(forKey: CacheKey.researchPrinciples)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Reject failed: \(error)")
            #endif
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
                label: String(result.chunk.content.prefix(50)),
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
                    graphEdges.append(GraphEdge(from: graphNodes[i].id, to: graphNodes[j].id, weight: weight))
                }
            }
        }

        // Client-side layout for mock data only
        computeMockLayout(nodes: &graphNodes, edges: graphEdges)
        self.nodes = graphNodes
        self.edges = graphEdges
    }

    private func computeMockLayout(nodes: inout [GraphNode], edges: [GraphEdge]) {
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
            for i in 0..<count { velocities[i] -= nodes[i].position * centerStrength }
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
}

// MARK: - NSColor Hex Init

extension NSColor {
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

    /// Hex string for server-side color matching
    var colorHex: String {
        switch self {
        case .conversation: return "#5AC8FA"
        case .fact: return "#4CD964"
        case .preference: return "#FF9500"
        case .decision: return "#FF3B30"
        case .actionItem: return "#AF52DE"
        case .research: return "#007AFF"
        case .system: return "#8E8E93"
        }
    }
}
