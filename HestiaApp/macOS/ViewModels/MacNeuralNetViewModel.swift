import SwiftUI
import AppKit
import SceneKit
import HestiaShared

// MARK: - Graph Mode

/// The two graph API modes: legacy co-occurrence vs. structured entity-fact.
enum GraphMode: String, CaseIterable {
    case legacy = "legacy"
    case facts  = "facts"

    var label: String {
        switch self {
        case .legacy: return "Memory"
        case .facts:  return "Knowledge"
        }
    }

    var icon: String {
        switch self {
        case .legacy: return "brain"
        case .facts:  return "point.3.connected.trianglepath.dotted"
        }
    }

    /// Default visible node types per mode.
    /// Legacy: principle-centric (P/F/D primary + structural connectors).
    /// Facts: entity-relationship focus.
    var defaultNodeTypes: Set<String> {
        switch self {
        case .legacy: return ["principle", "fact", "topic", "entity", "community"]
        case .facts:  return ["entity", "community", "episode", "fact"]
        }
    }
}

/// Source categories matching backend SourceCategory enum.
/// Used in facts mode to filter graph by provenance.
enum SourceCategoryFilter: String, CaseIterable {
    case conversation = "conversation"
    case imported = "imported"
    case web = "web"
    case tool = "tool"
    case userStatement = "user_statement"
    case appleEcosystem = "apple_ecosystem"
    case health = "health"
    case voice = "voice"

    var label: String {
        switch self {
        case .conversation:    return "Chat"
        case .imported:        return "Imported"
        case .web:             return "Web"
        case .tool:            return "Tools"
        case .userStatement:   return "User"
        case .appleEcosystem:  return "Apple"
        case .health:          return "Health"
        case .voice:           return "Voice"
        }
    }

    var icon: String {
        switch self {
        case .conversation:    return "bubble.left"
        case .imported:        return "square.and.arrow.down"
        case .web:             return "globe"
        case .tool:            return "wrench"
        case .userStatement:   return "person"
        case .appleEcosystem:  return "apple.logo"
        case .health:          return "heart"
        case .voice:           return "mic"
        }
    }
}

/// macOS ViewModel for the Neural Net 3D graph visualization
///
/// Fetches graph data from /v1/research/graph (server-side layout + edges).
/// Supports legacy (co-occurrence) and facts (entity-relationship) modes.
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

    // MARK: - Published State (Mode & Filters)

    @Published var graphMode: GraphMode = .legacy {
        didSet {
            if oldValue != graphMode {
                nodeTypeFilter = graphMode.defaultNodeTypes
            }
        }
    }
    @Published var nodeTypeFilter: Set<String> = GraphMode.legacy.defaultNodeTypes
    @Published var focusTopic: String = ""
    @Published var depthLimit: Int = 3
    @Published var activeDataSources: Set<String> = Set(["conversation", "mail", "notes", "calendar", "reminders", "health"])
    @Published var activeSourceCategories: Set<String> = Set(SourceCategoryFilter.allCases.map(\.rawValue))
    @Published var centerEntity: String = ""

    // MARK: - Published State (Time Slider — facts mode)

    @Published var timeSliderEnabled: Bool = false
    @Published var timeSliderValue: Double = 1.0  // 0.0 = oldest, 1.0 = now
    @Published var timeSliderDate: Date = Date()

    // MARK: - Published State (Durability Filter — Sprint 20A)
    @Published var minDurabilityFilter: Int = 0  // 0=show all, 1=contextual+, 2=durable+, 3=principled only

    /// Earliest fact date from the server metadata (set after first facts load)
    var earliestFactDate: Date = Calendar.current.date(byAdding: .year, value: -1, to: Date()) ?? Date()

    // MARK: - Published State (Principles)

    @Published var principles: [ResearchPrinciple] = []
    @Published var isLoadingPrinciples = false
    @Published var isDistilling = false
    @Published var principlesTotal: Int = 0
    @Published var principlesLoadError: String?

    // MARK: - Types

    struct GraphNode: Identifiable, Equatable {
        let id: String
        let content: String
        let nodeType: String       // "memory", "topic", "entity", "principle", "fact", "community", "episode"
        let category: String       // maps to ChunkType for memory nodes, EntityType for entity nodes
        let label: String
        let confidence: Double
        let weight: Double
        let topics: [String]
        let entities: [String]
        var position: SIMD3<Float> = .zero
        let colorHex: String
        let edgeType: String?      // populated on edges
        let lastActive: Date?      // Sprint 20A: for recency-based glow
        let maxDurability: Int     // Sprint 20A: 0-3 DIKW tier (from metadata)

        init(id: String, content: String, nodeType: String, category: String,
             label: String, confidence: Double, weight: Double,
             topics: [String] = [], entities: [String] = [],
             position: SIMD3<Float> = .zero, colorHex: String,
             edgeType: String? = nil, lastActive: Date? = nil,
             maxDurability: Int = 1) {
            self.id = id
            self.content = content
            self.nodeType = nodeType
            self.category = category
            self.label = label
            self.confidence = confidence
            self.weight = weight
            self.topics = topics
            self.entities = entities
            self.position = position
            self.colorHex = colorHex
            self.edgeType = edgeType
            self.lastActive = lastActive
            self.maxDurability = maxDurability
        }

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
            case "topic":     return "Topic"
            case "entity":    return "Entity"
            case "principle": return "Principle"
            case "community": return "Community"
            case "fact":      return "Fact"
            case "episode":   return "Episode"
            default:          return ChunkType(rawValue: category)?.displayName ?? category.capitalized
            }
        }

        var displayIcon: String {
            switch nodeType {
            case "topic":     return "tag"
            case "entity":    return "person.text.rectangle"
            case "principle": return "lightbulb"
            case "community": return "person.3"
            case "fact":      return "link"
            case "episode":   return "clock"
            default:          return ChunkType(rawValue: category)?.displayIcon ?? "circle"
            }
        }

        /// Node radius — blends weight with durability (Sprint 20A)
        /// Higher durability = larger node (DIKW: principled > durable > contextual)
        var radius: Float {
            let baseRadius = Float(0.12 + weight * 0.14) // Range: 0.12 - 0.26
            let durabilityBoost = Float(maxDurability) / 3.0 * 0.08 // 0.0 - 0.08
            return baseRadius + durabilityBoost // Total range: 0.12 - 0.34
        }
    }

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
            let sourcesParam: String? = activeDataSources.count == 6 ? nil : activeDataSources.sorted().joined(separator: ",")
            let centerEntityParam = centerEntity.isEmpty ? nil : centerEntity

            // Bi-temporal time slider (facts mode only)
            var pointInTimeParam: String? = nil
            if graphMode == .facts && timeSliderEnabled && timeSliderValue < 1.0 {
                let date = dateFromSliderValue(timeSliderValue)
                let formatter = ISO8601DateFormatter()
                pointInTimeParam = formatter.string(from: date)
            }

            // Source category filter (facts mode only)
            var sourceCategoriesParam: String? = nil
            if graphMode == .facts && activeSourceCategories.count < SourceCategoryFilter.allCases.count {
                sourceCategoriesParam = activeSourceCategories.sorted().joined(separator: ",")
            }

            let response = try await APIClient.shared.getResearchGraph(
                limit: 200,
                nodeTypes: nodeTypesParam,
                centerTopic: topicParam,
                mode: graphMode.rawValue,
                sources: sourcesParam,
                centerEntity: centerEntityParam,
                pointInTime: pointInTimeParam,
                sourceCategories: sourceCategoriesParam
            )
            applyGraphResponse(response)
            CacheManager.shared.cache(response, forKey: CacheKey.researchGraph, ttl: 300)

        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Server graph failed: \(error), using cache/mock")
            #endif
            if nodes.isEmpty {
                // Try stale cache before falling back to mock
                if let stale = CacheManager.shared.getStale(ResearchGraphResponse.self, forKey: CacheKey.researchGraph) {
                    applyGraphResponse(stale)
                } else {
                    loadMockGraph()
                }
            }
        }
    }

    private func applyGraphResponse(_ response: ResearchGraphResponse) {
        memoryCount = response.nodeCount

        // Parse earliest_fact_date from metadata for time slider range
        if let metaValue = response.metadata["earliest_fact_date"],
           case .string(let dateStr) = metaValue {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateStr) {
                earliestFactDate = date
            } else {
                // Try without fractional seconds
                let basic = ISO8601DateFormatter()
                if let date = basic.date(from: dateStr) {
                    earliestFactDate = date
                }
            }
        }

        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let isoFallback = ISO8601DateFormatter()
        isoFallback.formatOptions = [.withInternetDateTime]

        nodes = response.nodes.map { apiNode in
            // Parse lastActive date for recency glow
            var lastActiveDate: Date?
            if let dateStr = apiNode.lastActive {
                lastActiveDate = isoFormatter.date(from: dateStr) ?? isoFallback.date(from: dateStr)
            }

            // Extract max_durability from metadata (set by graph_builder for entity nodes)
            let maxDurability: Int
            if let metaVal = apiNode.metadata?["max_durability"], case .int(let d) = metaVal {
                maxDurability = d
            } else if let metaVal = apiNode.metadata?["max_durability"], case .double(let d) = metaVal {
                maxDurability = Int(d)
            } else {
                maxDurability = 1
            }

            return GraphNode(
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
                colorHex: apiNode.color,
                lastActive: lastActiveDate,
                maxDurability: maxDurability
            )
        }

        // Sprint 20A: Client-side durability filter
        if minDurabilityFilter > 0 {
            nodes = nodes.filter { $0.maxDurability >= minDurabilityFilter }
        }

        let nodeIdSet = Set(nodes.map(\.id))
        edges = response.edges.compactMap { apiEdge in
            // Only include edges where both endpoints survive filtering
            guard nodeIdSet.contains(apiEdge.fromId) && nodeIdSet.contains(apiEdge.toId) else {
                return nil
            }
            return GraphEdge(
                from: apiEdge.fromId,
                to: apiEdge.toId,
                weight: Float(apiEdge.weight),
                edgeType: apiEdge.edgeType
            )
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

    // MARK: - Time Slider Helpers

    /// Convert slider value (0.0–1.0) to a date between earliestFactDate and now.
    func dateFromSliderValue(_ value: Double) -> Date {
        let now = Date()
        let interval = now.timeIntervalSince(earliestFactDate)
        return earliestFactDate.addingTimeInterval(interval * value)
    }

    /// Human-readable label for the current slider position.
    var timeSliderLabel: String {
        if timeSliderValue >= 0.99 { return "Now" }
        let date = dateFromSliderValue(timeSliderValue)
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }

    // MARK: - Time Slider Debounce

    private var timeSliderTask: Task<Void, Never>?

    /// Debounced reload when the time slider changes (400ms delay).
    func onTimeSliderChanged() {
        timeSliderTask?.cancel()
        timeSliderTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 400_000_000)
            guard !Task.isCancelled else { return }
            await self?.loadGraph()
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

    /// Unique set of node types currently in the graph (for dynamic legend)
    var activeNodeTypes: [String] {
        Array(Set(nodes.map(\.nodeType))).sorted()
    }

    // MARK: - Principles

    func loadPrinciples(status: String? = nil) async {
        isLoadingPrinciples = true
        defer { isLoadingPrinciples = false }

        // Fresh cache → show immediately
        if let cached = CacheManager.shared.get(PrincipleListResponse.self, forKey: CacheKey.researchPrinciples) {
            principles = cached.principles
            principlesTotal = cached.total
            principlesLoadError = nil
        }

        do {
            let response = try await APIClient.shared.getPrinciples(status: status)
            principles = response.principles
            principlesTotal = response.total
            principlesLoadError = nil
            CacheManager.shared.cache(response, forKey: CacheKey.researchPrinciples, ttl: 300)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Failed to load principles: \(error)")
            #endif
            // Stale cache fallback — better to show old data than nothing
            if principles.isEmpty,
               let stale = CacheManager.shared.getStale(PrincipleListResponse.self, forKey: CacheKey.researchPrinciples),
               !stale.principles.isEmpty {
                principles = stale.principles
                principlesTotal = stale.total
                principlesLoadError = nil
            } else if principles.isEmpty {
                principlesLoadError = "Could not reach server"
            }
        }
    }

    func distillPrinciples() async {
        isDistilling = true
        defer { isDistilling = false }

        do {
            let result = try await APIClient.shared.distillPrinciples()
            #if DEBUG
            print("[MacNeuralNetViewModel] Distilled \(result.principlesExtracted) principles")
            #endif
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
            if let _ = principles.firstIndex(where: { $0.id == id }) {
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
            if let _ = principles.firstIndex(where: { $0.id == id }) {
                await loadPrinciples()
            }
            CacheManager.shared.invalidate(forKey: CacheKey.researchPrinciples)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Reject failed: \(error)")
            #endif
        }
    }

    func updatePrincipleContent(_ id: String, content: String) async {
        do {
            _ = try await APIClient.shared.updatePrinciple(id, content: content)
            await loadPrinciples()
            CacheManager.shared.invalidate(forKey: CacheKey.researchPrinciples)
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Update principle failed: \(error)")
            #endif
        }
    }

    /// Mark a fact as outdated/superseded via the research API.
    func markFactOutdated(_ id: String) async {
        do {
            _ = try await APIClient.shared.invalidateFact(id, reason: "Marked outdated by user")
            // Reload graph to reflect the change
            await loadGraph()
        } catch {
            #if DEBUG
            print("[MacNeuralNetViewModel] Fact invalidation failed: \(error)")
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
