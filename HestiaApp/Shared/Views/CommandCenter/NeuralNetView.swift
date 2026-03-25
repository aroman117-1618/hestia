import SwiftUI
import HestiaShared
import SceneKit

/// Interactive 3D Neural Net graph visualization using SceneKit
///
/// Renders knowledge graph nodes as glowing shapes connected by styled edges.
/// Supports pan, zoom, and rotate via SceneKit's camera controls.
/// Tap a node to select it and see its details.
struct NeuralNetView: View {
    @StateObject private var viewModel = NeuralNetViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerBar

            // 3D Graph
            ZStack {
                if viewModel.isLoading {
                    loadingState
                } else if viewModel.nodes.isEmpty {
                    emptyState
                } else {
                    SceneKitGraphView(
                        nodes: viewModel.nodes,
                        edges: viewModel.edges,
                        selectedNode: $viewModel.selectedNode
                    )
                    .clipped()

                    // Legend overlay (bottom-left) — dynamic
                    legendOverlay

                    // Node count badge (top-right)
                    nodeCountBadge
                }
            }
            .frame(height: 320)
            .background(Color.bgBase.opacity(0.3))
            .cornerRadius(CornerRadius.card)
            .clipped()

            // Selected node detail
            if let node = viewModel.selectedNode {
                nodeDetailCard(node)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .onAppear {
            Task {
                await viewModel.loadGraph()
            }
        }
    }

    // MARK: - Header

    private var headerBar: some View {
        HStack {
            Image(systemName: "brain.head.profile")
                .foregroundColor(.textSecondary)

            Text("Neural Net")
                .font(.headline)
                .foregroundColor(.textPrimary)

            Spacer()

            if viewModel.memoryCount > 0 {
                Text("\(viewModel.memoryCount) nodes")
                    .font(.caption)
                    .foregroundColor(.textSecondary)
            }
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.sm)
    }

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: Spacing.md) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                .scaleEffect(1.2)

            Text("Mapping neural connections...")
                .font(.caption)
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "brain")
                .font(.system(size: 32))
                .foregroundColor(.textTertiary)

            Text("No memories yet")
                .font(.subheadline)
                .foregroundColor(.textSecondary)

            Text("Start chatting to build your neural net")
                .font(.caption)
                .foregroundColor(.textTertiary)
        }
    }

    // MARK: - Dynamic Legend Overlay

    /// All node types with their display metadata
    private static let legendMap: [String: (label: String, color: Color)] = [
        "memory":    ("Memory",    Color(red: 0.5, green: 0.5, blue: 0.5)),
        "topic":     ("Topic",     Color(red: 1.0, green: 0.84, blue: 0.04)),
        "entity":    ("Entity",    Color(red: 0.19, green: 0.82, blue: 0.35)),
        "principle": ("Principle", Color(red: 0.75, green: 0.35, blue: 0.95)),
        "community": ("Community", Color(red: 1.0, green: 0.22, blue: 0.37)),
        "episode":   ("Episode",   Color(red: 0.35, green: 0.78, blue: 0.98)),
        "fact":      ("Fact",      Color(red: 0.39, green: 0.82, blue: 1.0)),
    ]

    private var legendOverlay: some View {
        let activeTypes = Array(Set(viewModel.nodes.map(\.nodeType))).sorted()

        return VStack(alignment: .leading, spacing: 3) {
            ForEach(activeTypes, id: \.self) { nodeType in
                if let entry = Self.legendMap[nodeType] {
                    legendDot(color: entry.color, label: entry.label)
                }
            }

            if activeTypes.contains("memory") {
                legendDot(color: Color(UIColor(red: 0.6, green: 0.3, blue: 0.9, alpha: 1)), label: "Preference")
                legendDot(color: Color(UIColor(red: 0.2, green: 0.5, blue: 1.0, alpha: 1)), label: "Fact")
                legendDot(color: Color(UIColor(red: 1.0, green: 0.6, blue: 0.2, alpha: 1)), label: "Decision")
                legendDot(color: Color(UIColor(red: 1.0, green: 0.3, blue: 0.3, alpha: 1)), label: "Action")
                legendDot(color: Color(UIColor(red: 0.2, green: 0.8, blue: 0.6, alpha: 1)), label: "Research")
            }
        }
        .padding(Spacing.sm)
        .background(Color.bgBase.opacity(0.5))
        .cornerRadius(8)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
        .padding(Spacing.sm)
    }

    private func legendDot(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)

            Text(label)
                .font(.system(size: 9))
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Node Count Badge

    private var nodeCountBadge: some View {
        Text("\(viewModel.nodes.count) nodes")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.textSecondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.bgBase.opacity(0.5))
            .cornerRadius(8)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
            .padding(Spacing.sm)
    }

    // MARK: - Node Detail Card

    private func nodeDetailCard(_ node: NeuralNetViewModel.GraphNode) -> some View {
        HStack(spacing: Spacing.sm) {
            // Type indicator
            Circle()
                .fill(Color(node.color))
                .frame(width: 12, height: 12)

            VStack(alignment: .leading, spacing: 2) {
                Text(node.displayName)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.textPrimary.opacity(0.8))

                Text(node.content)
                    .font(.caption2)
                    .foregroundColor(.textSecondary)
                    .lineLimit(2)
            }

            Spacer()

            // Confidence badge
            Text("\(Int(node.confidence * 100))%")
                .font(.caption2.weight(.bold))
                .foregroundColor(.textSecondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.bgOverlay)
                .cornerRadius(4)

            // Dismiss button
            Button {
                withAnimation(.hestiaQuick) {
                    viewModel.selectedNode = nil
                }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.textTertiary)
                    .font(.system(size: 16))
            }
        }
        .padding(Spacing.sm)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.small)
        .padding(.top, Spacing.xs)
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }
}

// MARK: - SceneKit Graph View (UIViewRepresentable)

/// Wraps an SCNView to render the 3D force-directed graph
struct SceneKitGraphView: UIViewRepresentable {
    let nodes: [NeuralNetViewModel.GraphNode]
    let edges: [NeuralNetViewModel.GraphEdge]
    @Binding var selectedNode: NeuralNetViewModel.GraphNode?

    func makeUIView(context: Context) -> SCNView {
        let sceneView = SCNView()
        sceneView.backgroundColor = .clear
        sceneView.autoenablesDefaultLighting = false
        sceneView.allowsCameraControl = true
        sceneView.antialiasingMode = .multisampling4X
        sceneView.preferredFramesPerSecond = 60

        // Build the scene
        let scene = buildScene()
        sceneView.scene = scene

        // Add tap gesture
        let tapGesture = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleTap(_:))
        )
        sceneView.addGestureRecognizer(tapGesture)
        context.coordinator.sceneView = sceneView

        return sceneView
    }

    func updateUIView(_ sceneView: SCNView, context: Context) {
        // Only rebuild scene when nodes/edges actually change (not on selectedNode changes)
        let nodeIds = Set(nodes.map(\.id))
        let cachedIds = Set(context.coordinator.nodes.map(\.id))
        if nodeIds != cachedIds || nodes.count != context.coordinator.nodes.count {
            let scene = buildScene()
            sceneView.scene = scene
            context.coordinator.nodes = nodes
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Scene Construction

    private func buildScene() -> SCNScene {
        let scene = SCNScene()
        scene.background.contents = UIColor.clear

        // Ambient light — soft overall illumination
        let ambientLight = SCNNode()
        ambientLight.light = SCNLight()
        ambientLight.light?.type = .ambient
        ambientLight.light?.intensity = 400
        ambientLight.light?.color = UIColor(white: 0.6, alpha: 1)
        scene.rootNode.addChildNode(ambientLight)

        // Directional light — gives depth/shadow cues
        let directionalLight = SCNNode()
        directionalLight.light = SCNLight()
        directionalLight.light?.type = .directional
        directionalLight.light?.intensity = 600
        directionalLight.light?.color = UIColor(white: 0.8, alpha: 1)
        directionalLight.position = SCNVector3(5, 10, 8)
        directionalLight.look(at: SCNVector3Zero)
        scene.rootNode.addChildNode(directionalLight)

        // Camera
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.camera?.zNear = 0.1
        cameraNode.camera?.zFar = 100
        cameraNode.camera?.fieldOfView = 50
        cameraNode.position = SCNVector3(0, 0, 8)
        cameraNode.look(at: SCNVector3Zero)
        scene.rootNode.addChildNode(cameraNode)

        // Build node index for edge lookups
        var nodePositions: [String: SIMD3<Float>] = [:]
        for node in nodes {
            nodePositions[node.id] = node.position
        }

        // Add edges FIRST (so nodes render on top)
        for edge in edges {
            guard let fromPos = nodePositions[edge.fromId],
                  let toPos = nodePositions[edge.toId] else { continue }

            let edgeNode = createEdgeNode(from: fromPos, to: toPos, edge: edge)
            scene.rootNode.addChildNode(edgeNode)
        }

        // Add nodes with per-type geometry
        for node in nodes {
            let sceneNode = createNodeGeometry(for: node)
            scene.rootNode.addChildNode(sceneNode)
        }

        return scene
    }

    // MARK: - Node Geometry (shape per nodeType)

    private func createNodeGeometry(for graphNode: NeuralNetViewModel.GraphNode) -> SCNNode {
        let r = CGFloat(graphNode.radius)
        let geometry: SCNGeometry

        switch graphNode.nodeType {
        case "topic":
            let sphere = SCNSphere(radius: r)
            sphere.segmentCount = 4
            geometry = sphere

        case "entity":
            let side = r * 1.6
            geometry = SCNBox(width: side, height: side, length: side, chamferRadius: side * 0.1)

        case "principle":
            geometry = SCNTorus(ringRadius: r * 1.0, pipeRadius: r * 0.35)

        case "community":
            let sphere = SCNSphere(radius: r * 2.0)
            sphere.segmentCount = 32
            let material = SCNMaterial()
            material.diffuse.contents = graphNode.color.withAlphaComponent(0.15)
            material.emission.contents = graphNode.color.withAlphaComponent(0.08)
            material.lightingModel = .constant
            material.isDoubleSided = true
            sphere.materials = [material]

            let node = SCNNode(geometry: sphere)
            node.position = SCNVector3(graphNode.position.x, graphNode.position.y, graphNode.position.z)
            node.name = graphNode.id
            return node

        case "episode":
            geometry = SCNCapsule(capRadius: r * 0.6, height: r * 2.5)

        case "fact":
            geometry = SCNCylinder(radius: r * 0.8, height: r * 0.4)

        default:
            let sphere = SCNSphere(radius: r)
            sphere.segmentCount = 24
            geometry = sphere
        }

        // Material with glow effect
        let material = SCNMaterial()
        material.diffuse.contents = graphNode.color
        material.emission.contents = graphNode.color.withAlphaComponent(0.4)
        material.lightingModel = .physicallyBased
        material.metalness.contents = 0.3
        material.roughness.contents = 0.6
        geometry.materials = [material]

        let node = SCNNode(geometry: geometry)
        node.position = SCNVector3(
            graphNode.position.x,
            graphNode.position.y,
            graphNode.position.z
        )
        node.name = graphNode.id

        // Subtle pulse animation for visual life
        let pulse = SCNAction.sequence([
            SCNAction.scale(to: 1.05, duration: 1.5),
            SCNAction.scale(to: 0.95, duration: 1.5)
        ])
        node.runAction(SCNAction.repeatForever(pulse))

        return node
    }

    // MARK: - Edge Creation (styled by edgeType)

    private func createEdgeNode(from: SIMD3<Float>, to: SIMD3<Float>, edge: NeuralNetViewModel.GraphEdge) -> SCNNode {
        let delta = to - from
        let distance = simd_length(delta)
        guard distance > 0.01 else { return SCNNode() }

        let styling = edgeStyling(for: edge.edgeType, weight: edge.weight)

        let cylinder = SCNCylinder(radius: CGFloat(styling.radius), height: CGFloat(distance))
        let material = SCNMaterial()
        material.diffuse.contents = styling.color
        material.lightingModel = .constant
        cylinder.materials = [material]

        let edgeNode = SCNNode(geometry: cylinder)

        // Position at midpoint
        let midpoint = (from + to) / 2.0
        edgeNode.position = SCNVector3(midpoint.x, midpoint.y, midpoint.z)

        // Rotate to align with the edge direction
        let yAxis = SIMD3<Float>(0, 1, 0)
        let direction = simd_normalize(delta)

        let cross = simd_cross(yAxis, direction)
        let crossLen = simd_length(cross)
        let dot = simd_dot(yAxis, direction)

        if crossLen > 0.001 {
            let angle = atan2(crossLen, dot)
            let axis = simd_normalize(cross)
            edgeNode.rotation = SCNVector4(axis.x, axis.y, axis.z, angle)
        } else if dot < 0 {
            edgeNode.rotation = SCNVector4(1, 0, 0, Float.pi)
        }

        return edgeNode
    }

    private func edgeStyling(for edgeType: String, weight: Float) -> (radius: Float, color: UIColor) {
        switch edgeType {
        case "relationship":
            let r = 0.012 + weight * 0.015
            return (r, UIColor(red: 1.0, green: 0.6, blue: 0.2, alpha: CGFloat(0.15 + weight * 0.25)))
        case "supersedes":
            return (0.012, UIColor(red: 1.0, green: 0.2, blue: 0.2, alpha: 0.3))
        case "principle_source":
            return (0.010, UIColor(red: 0.75, green: 0.35, blue: 0.95, alpha: 0.25))
        case "community_member":
            return (0.005, UIColor(red: 1.0, green: 0.2, blue: 0.37, alpha: 0.15))
        case "topic_membership":
            return (0.005, UIColor(red: 1.0, green: 0.84, blue: 0.04, alpha: 0.15))
        case "entity_membership":
            return (0.005, UIColor(red: 0.19, green: 0.82, blue: 0.35, alpha: 0.15))
        case "semantic":
            return (0.008, UIColor(red: 0.35, green: 0.78, blue: 0.98, alpha: 0.20))
        default:
            let r = 0.008 + weight * 0.012
            return (r, UIColor.white.withAlphaComponent(CGFloat(0.08 + weight * 0.15)))
        }
    }

    // MARK: - Coordinator (Tap Handling)

    @MainActor
    class Coordinator: NSObject {
        var parent: SceneKitGraphView
        var nodes: [NeuralNetViewModel.GraphNode] = []
        weak var sceneView: SCNView?

        init(_ parent: SceneKitGraphView) {
            self.parent = parent
            self.nodes = parent.nodes
        }

        @objc func handleTap(_ gesture: UITapGestureRecognizer) {
            guard let sceneView = sceneView else { return }
            let location = gesture.location(in: sceneView)

            let hitNodeNames: [String] = sceneView.hitTest(location, options: [
                .searchMode: SCNHitTestSearchMode.closest.rawValue,
                .boundingBoxOnly: true
            ]).compactMap { $0.node.name }

            for nodeName in hitNodeNames {
                if let graphNode = nodes.first(where: { $0.id == nodeName }) {
                    withAnimation(.hestiaQuick) {
                        self.parent.selectedNode = graphNode
                    }
                    return
                }
            }

            withAnimation(.hestiaQuick) {
                self.parent.selectedNode = nil
            }
        }
    }
}

// MARK: - Preview

struct NeuralNetView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.bgBase.ignoresSafeArea()
            NeuralNetView()
        }
    }
}
