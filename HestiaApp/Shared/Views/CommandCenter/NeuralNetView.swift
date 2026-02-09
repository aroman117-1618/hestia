import SwiftUI
import SceneKit

/// Interactive 3D Neural Net graph visualization using SceneKit
///
/// Renders memory chunks as glowing spheres connected by translucent edges.
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

                    // Legend overlay (bottom-left)
                    legendOverlay

                    // Node count badge (top-right)
                    nodeCountBadge
                }
            }
            .frame(height: 320)
            .background(Color.black.opacity(0.3))
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
                .foregroundColor(.white.opacity(0.7))

            Text("Neural Net")
                .font(.headline)
                .foregroundColor(.white)

            Spacer()

            if viewModel.memoryCount > 0 {
                Text("\(viewModel.memoryCount) memories")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
            }
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.sm)
    }

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: Spacing.md) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                .scaleEffect(1.2)

            Text("Mapping neural connections...")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "brain")
                .font(.system(size: 32))
                .foregroundColor(.white.opacity(0.3))

            Text("No memories yet")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.5))

            Text("Start chatting to build your neural net")
                .font(.caption)
                .foregroundColor(.white.opacity(0.3))
        }
    }

    // MARK: - Legend Overlay

    private var legendOverlay: some View {
        VStack(alignment: .leading, spacing: 3) {
            legendDot(color: Color(UIColor(red: 0.6, green: 0.3, blue: 0.9, alpha: 1)), label: "Preference")
            legendDot(color: Color(UIColor(red: 0.2, green: 0.5, blue: 1.0, alpha: 1)), label: "Fact")
            legendDot(color: Color(UIColor(red: 1.0, green: 0.6, blue: 0.2, alpha: 1)), label: "Decision")
            legendDot(color: Color(UIColor(red: 1.0, green: 0.3, blue: 0.3, alpha: 1)), label: "Action")
            legendDot(color: Color(UIColor(red: 0.2, green: 0.8, blue: 0.6, alpha: 1)), label: "Research")
        }
        .padding(Spacing.sm)
        .background(Color.black.opacity(0.5))
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
                .foregroundColor(.white.opacity(0.6))
        }
    }

    // MARK: - Node Count Badge

    private var nodeCountBadge: some View {
        Text("\(viewModel.nodes.count) nodes")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.white.opacity(0.5))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.black.opacity(0.5))
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
                Text(node.chunkType.rawValue.capitalized)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.white.opacity(0.8))

                Text(node.content)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.6))
                    .lineLimit(2)
            }

            Spacer()

            // Confidence badge
            Text("\(Int(node.confidence * 100))%")
                .font(.caption2.weight(.bold))
                .foregroundColor(.white.opacity(0.7))
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.white.opacity(0.1))
                .cornerRadius(4)

            // Dismiss button
            Button {
                withAnimation(.hestiaQuick) {
                    viewModel.selectedNode = nil
                }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.white.opacity(0.4))
                    .font(.system(size: 16))
            }
        }
        .padding(Spacing.sm)
        .background(Color.white.opacity(0.08))
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

            let edgeNode = createEdgeNode(from: fromPos, to: toPos, weight: edge.weight)
            scene.rootNode.addChildNode(edgeNode)
        }

        // Add nodes
        for node in nodes {
            let sphereNode = createSphereNode(for: node)
            scene.rootNode.addChildNode(sphereNode)
        }

        return scene
    }

    // MARK: - Node Creation

    private func createSphereNode(for graphNode: NeuralNetViewModel.GraphNode) -> SCNNode {
        let sphere = SCNSphere(radius: CGFloat(graphNode.radius))
        sphere.segmentCount = 24

        // Material with glow effect
        let material = SCNMaterial()
        material.diffuse.contents = graphNode.color
        material.emission.contents = graphNode.color.withAlphaComponent(0.4)
        material.lightingModel = .physicallyBased
        material.metalness.contents = 0.3
        material.roughness.contents = 0.6
        sphere.materials = [material]

        let node = SCNNode(geometry: sphere)
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

    // MARK: - Edge Creation

    private func createEdgeNode(from: SIMD3<Float>, to: SIMD3<Float>, weight: Float) -> SCNNode {
        let delta = to - from
        let distance = simd_length(delta)
        guard distance > 0.01 else { return SCNNode() }

        // Cylinder along Y-axis, then rotated
        let cylinder = SCNCylinder(radius: CGFloat(0.008 + weight * 0.012), height: CGFloat(distance))
        let material = SCNMaterial()
        material.diffuse.contents = UIColor.white.withAlphaComponent(CGFloat(0.08 + weight * 0.15))
        material.lightingModel = .constant
        cylinder.materials = [material]

        let edgeNode = SCNNode(geometry: cylinder)

        // Position at midpoint
        let midpoint = (from + to) / 2.0
        edgeNode.position = SCNVector3(midpoint.x, midpoint.y, midpoint.z)

        // Rotate to align with the edge direction
        let yAxis = SIMD3<Float>(0, 1, 0)
        let direction = simd_normalize(delta)

        // Quaternion rotation from Y-axis to edge direction
        let cross = simd_cross(yAxis, direction)
        let crossLen = simd_length(cross)
        let dot = simd_dot(yAxis, direction)

        if crossLen > 0.001 {
            let angle = atan2(crossLen, dot)
            let axis = simd_normalize(cross)
            edgeNode.rotation = SCNVector4(axis.x, axis.y, axis.z, angle)
        } else if dot < 0 {
            // Anti-parallel: rotate 180 degrees around any perpendicular axis
            edgeNode.rotation = SCNVector4(1, 0, 0, Float.pi)
        }

        return edgeNode
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

            // Extract node names from hit results on the current thread
            // to avoid sending non-Sendable SCNHitTestResult across boundaries
            let hitNodeNames: [String] = sceneView.hitTest(location, options: [
                .searchMode: SCNHitTestSearchMode.closest.rawValue,
                .boundingBoxOnly: true
            ]).compactMap { $0.node.name }

            // Find the first hit node that matches a graph node
            for nodeName in hitNodeNames {
                if let graphNode = nodes.first(where: { $0.id == nodeName }) {
                    withAnimation(.hestiaQuick) {
                        self.parent.selectedNode = graphNode
                    }
                    return
                }
            }

            // Tapped empty space — deselect
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
            Color.black.ignoresSafeArea()
            NeuralNetView()
        }
    }
}
