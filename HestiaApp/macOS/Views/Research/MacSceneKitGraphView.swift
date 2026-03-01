import SwiftUI
import AppKit
@preconcurrency import SceneKit

/// macOS SceneKit 3D graph — NSViewRepresentable wrapper
///
/// Supports:
/// - Orbit/zoom/pan via SceneKit's camera controls (trackpad gestures)
/// - Click to select a node
/// - Drag to move individual nodes in the camera's view plane
struct MacSceneKitGraphView: NSViewRepresentable {
    let nodes: [MacNeuralNetViewModel.GraphNode]
    let edges: [MacNeuralNetViewModel.GraphEdge]
    @Binding var selectedNode: MacNeuralNetViewModel.GraphNode?
    var onNodeMoved: ((String, SIMD3<Float>) -> Void)?

    func makeNSView(context: Context) -> SCNView {
        let sceneView = SCNView()
        sceneView.backgroundColor = .clear
        sceneView.autoenablesDefaultLighting = false
        sceneView.allowsCameraControl = true
        sceneView.antialiasingMode = .multisampling4X

        let scene = buildScene()
        sceneView.scene = scene

        // Click gesture for selection
        let clickGesture = NSClickGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleClick(_:))
        )
        sceneView.addGestureRecognizer(clickGesture)

        // Drag gesture for moving nodes — requires disabling camera control during drag
        let panGesture = NSPanGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleDrag(_:))
        )
        sceneView.addGestureRecognizer(panGesture)

        context.coordinator.sceneView = sceneView

        return sceneView
    }

    func updateNSView(_ sceneView: SCNView, context: Context) {
        let nodeIds = Set(nodes.map(\.id))
        let cachedIds = Set(context.coordinator.cachedNodeIds)

        if nodeIds != cachedIds || nodes.count != context.coordinator.cachedNodeIds.count {
            // Full rebuild — nodes changed
            let scene = buildScene()
            sceneView.scene = scene
            context.coordinator.cachedNodeIds = Array(nodeIds)
            context.coordinator.nodes = nodes
        } else {
            // Incremental update — just sync positions (for drag feedback)
            guard let rootNode = sceneView.scene?.rootNode else { return }
            for node in nodes {
                if let scnNode = rootNode.childNode(withName: node.id, recursively: false) {
                    let current = scnNode.position
                    let target = SCNVector3(node.position.x, node.position.y, node.position.z)
                    // Only update if position actually changed (avoids jitter during drag)
                    if abs(current.x - target.x) > 0.001 ||
                       abs(current.y - target.y) > 0.001 ||
                       abs(current.z - target.z) > 0.001 {
                        scnNode.position = target
                    }
                }
            }
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Scene Construction

    private func buildScene() -> SCNScene {
        let scene = SCNScene()
        scene.background.contents = NSColor.clear

        // Ambient light
        let ambientLight = SCNNode()
        ambientLight.light = SCNLight()
        ambientLight.light?.type = .ambient
        ambientLight.light?.intensity = 400
        ambientLight.light?.color = NSColor(white: 0.6, alpha: 1)
        scene.rootNode.addChildNode(ambientLight)

        // Directional light
        let directionalLight = SCNNode()
        directionalLight.light = SCNLight()
        directionalLight.light?.type = .directional
        directionalLight.light?.intensity = 600
        directionalLight.light?.color = NSColor(white: 0.8, alpha: 1)
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

        // Node position lookup for edges
        var nodePositions: [String: SIMD3<Float>] = [:]
        for node in nodes {
            nodePositions[node.id] = node.position
        }

        // Edges first (render behind nodes)
        for edge in edges {
            guard let fromPos = nodePositions[edge.fromId],
                  let toPos = nodePositions[edge.toId] else { continue }
            let edgeNode = createEdgeNode(from: fromPos, to: toPos, weight: edge.weight)
            scene.rootNode.addChildNode(edgeNode)
        }

        // Nodes
        for node in nodes {
            let sphereNode = createSphereNode(for: node)
            scene.rootNode.addChildNode(sphereNode)
        }

        return scene
    }

    private func createSphereNode(for graphNode: MacNeuralNetViewModel.GraphNode) -> SCNNode {
        let sphere = SCNSphere(radius: CGFloat(graphNode.radius))
        sphere.segmentCount = 24

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

        // Subtle pulse animation
        let pulse = SCNAction.sequence([
            SCNAction.scale(to: 1.05, duration: 1.5),
            SCNAction.scale(to: 0.95, duration: 1.5)
        ])
        node.runAction(SCNAction.repeatForever(pulse))

        return node
    }

    private func createEdgeNode(from: SIMD3<Float>, to: SIMD3<Float>, weight: Float) -> SCNNode {
        let delta = to - from
        let distance = simd_length(delta)
        guard distance > 0.01 else { return SCNNode() }

        let cylinder = SCNCylinder(radius: CGFloat(0.008 + weight * 0.012), height: CGFloat(distance))
        let material = SCNMaterial()
        material.diffuse.contents = NSColor.white.withAlphaComponent(CGFloat(0.08 + weight * 0.15))
        material.lightingModel = .constant
        cylinder.materials = [material]

        let edgeNode = SCNNode(geometry: cylinder)

        let midpoint = (from + to) / 2.0
        edgeNode.position = SCNVector3(midpoint.x, midpoint.y, midpoint.z)

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

    // MARK: - Coordinator (Click + Drag)

    @MainActor
    class Coordinator: NSObject {
        var parent: MacSceneKitGraphView
        var nodes: [MacNeuralNetViewModel.GraphNode] = []
        var cachedNodeIds: [String] = []
        weak var sceneView: SCNView?

        // Drag state
        private var draggedNodeName: String?
        private var dragStartScreenZ: CGFloat = 0

        init(_ parent: MacSceneKitGraphView) {
            self.parent = parent
            self.nodes = parent.nodes
            self.cachedNodeIds = parent.nodes.map(\.id)
        }

        @objc func handleClick(_ gesture: NSClickGestureRecognizer) {
            guard let sceneView = sceneView else { return }
            let location = gesture.location(in: sceneView)

            let hitNodeNames: [String] = sceneView.hitTest(location, options: [
                .searchMode: SCNHitTestSearchMode.closest.rawValue,
                .boundingBoxOnly: true as NSNumber
            ]).compactMap { $0.node.name }

            for nodeName in hitNodeNames {
                if let graphNode = nodes.first(where: { $0.id == nodeName }) {
                    DispatchQueue.main.async { [weak self] in
                        withAnimation(.easeInOut(duration: 0.15)) {
                            self?.parent.selectedNode = graphNode
                        }
                    }
                    return
                }
            }

            DispatchQueue.main.async { [weak self] in
                withAnimation(.easeInOut(duration: 0.15)) {
                    self?.parent.selectedNode = nil
                }
            }
        }

        @objc func handleDrag(_ gesture: NSPanGestureRecognizer) {
            guard let sceneView = sceneView else { return }
            let location = gesture.location(in: sceneView)

            switch gesture.state {
            case .began:
                // Hit-test to find which node we're dragging
                let hits = sceneView.hitTest(location, options: [
                    .searchMode: SCNHitTestSearchMode.closest.rawValue,
                    .boundingBoxOnly: true as NSNumber
                ])

                for hit in hits {
                    if let name = hit.node.name,
                       nodes.contains(where: { $0.id == name }) {
                        draggedNodeName = name
                        // Disable camera control while dragging a node
                        sceneView.allowsCameraControl = false
                        // Remember the screen-space Z for consistent depth
                        let projected = sceneView.projectPoint(hit.node.position)
                        dragStartScreenZ = CGFloat(projected.z)
                        return
                    }
                }
                // No node hit — let camera control handle it
                draggedNodeName = nil

            case .changed:
                guard let name = draggedNodeName,
                      let scnNode = sceneView.scene?.rootNode.childNode(withName: name, recursively: false) else { return }

                // Unproject the current mouse position at the same depth
                let screenPoint = SCNVector3(Float(location.x), Float(location.y), Float(dragStartScreenZ))
                let worldPoint = sceneView.unprojectPoint(screenPoint)

                scnNode.position = worldPoint

                // Notify the ViewModel
                let newPos = SIMD3<Float>(Float(worldPoint.x), Float(worldPoint.y), Float(worldPoint.z))
                DispatchQueue.main.async { [weak self] in
                    self?.parent.onNodeMoved?(name, newPos)
                }

            case .ended, .cancelled:
                if draggedNodeName != nil {
                    sceneView.allowsCameraControl = true
                    draggedNodeName = nil
                }

            default:
                break
            }
        }
    }
}
