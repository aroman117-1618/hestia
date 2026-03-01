import SwiftUI
import AppKit
@preconcurrency import SceneKit

/// macOS SceneKit 3D graph — NSViewRepresentable wrapper
///
/// Supports:
/// - Orbit/zoom/pan via SceneKit's camera controls (trackpad gestures)
/// - Click to select a node
/// - Hover to highlight nodes (mouseMoved via custom SCNView subclass)
/// - Selection ring glow on selected node
struct MacSceneKitGraphView: NSViewRepresentable {
    let nodes: [MacNeuralNetViewModel.GraphNode]
    let edges: [MacNeuralNetViewModel.GraphEdge]
    @Binding var selectedNode: MacNeuralNetViewModel.GraphNode?
    @Binding var hoveredNode: MacNeuralNetViewModel.GraphNode?

    func makeNSView(context: Context) -> HoverableSCNView {
        let sceneView = HoverableSCNView()
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

        context.coordinator.sceneView = sceneView
        sceneView.coordinator = context.coordinator

        return sceneView
    }

    func updateNSView(_ sceneView: HoverableSCNView, context: Context) {
        let nodeIds = Set(nodes.map(\.id))
        let cachedIds = Set(context.coordinator.cachedNodeIds)

        if nodeIds != cachedIds {
            // Full rebuild — nodes changed
            let scene = buildScene()
            sceneView.scene = scene
            context.coordinator.cachedNodeIds = Array(nodeIds)
            context.coordinator.nodes = nodes
        }

        // Update selection ring
        updateSelectionRing(in: sceneView, context: context)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Selection Ring

    private func updateSelectionRing(in sceneView: SCNView, context: Context) {
        guard let rootNode = sceneView.scene?.rootNode else { return }

        // Remove old ring (stop actions first to prevent leaked action objects)
        if let oldRing = rootNode.childNode(withName: "__selection_ring__", recursively: false) {
            oldRing.removeAllActions()
            oldRing.removeFromParentNode()
        }

        // Add new ring if node is selected
        guard let selected = selectedNode,
              let targetNode = rootNode.childNode(withName: selected.id, recursively: false) else { return }

        let ringRadius = CGFloat(selected.radius * 1.6)
        let ring = SCNTorus(ringRadius: ringRadius, pipeRadius: ringRadius * 0.06)
        let material = SCNMaterial()
        material.diffuse.contents = selected.color.withAlphaComponent(0.3)
        material.emission.contents = selected.color
        material.lightingModel = .constant
        ring.materials = [material]

        let ringNode = SCNNode(geometry: ring)
        ringNode.name = "__selection_ring__"
        ringNode.position = targetNode.position

        // Slow rotation for visual interest
        let rotate = SCNAction.rotateBy(x: 0, y: CGFloat.pi * 2, z: 0, duration: 4)
        ringNode.runAction(SCNAction.repeatForever(rotate))

        rootNode.addChildNode(ringNode)
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

    // MARK: - Coordinator (Click + Hover)

    @MainActor
    class Coordinator: NSObject {
        var parent: MacSceneKitGraphView
        var nodes: [MacNeuralNetViewModel.GraphNode] = []
        var cachedNodeIds: [String] = []
        weak var sceneView: SCNView?

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
            ]).compactMap { $0.node.name }.filter { !$0.hasPrefix("__") }

            for nodeName in hitNodeNames {
                if let graphNode = nodes.first(where: { $0.id == nodeName }) {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        parent.selectedNode = graphNode
                    }
                    return
                }
            }

            withAnimation(.easeInOut(duration: 0.15)) {
                parent.selectedNode = nil
            }
        }

        func handleMouseMoved(at location: CGPoint) {
            guard let sceneView = sceneView else { return }

            let hitNodeNames: [String] = sceneView.hitTest(location, options: [
                .searchMode: SCNHitTestSearchMode.closest.rawValue,
                .boundingBoxOnly: true as NSNumber
            ]).compactMap { $0.node.name }.filter { !$0.hasPrefix("__") }

            for nodeName in hitNodeNames {
                if let graphNode = nodes.first(where: { $0.id == nodeName }) {
                    if parent.hoveredNode?.id != graphNode.id {
                        parent.hoveredNode = graphNode
                    }
                    return
                }
            }

            if parent.hoveredNode != nil {
                parent.hoveredNode = nil
            }
        }
    }
}

// MARK: - Custom SCNView subclass for mouse hover tracking

@MainActor
class HoverableSCNView: SCNView {
    weak var coordinator: MacSceneKitGraphView.Coordinator?

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        // Remove existing tracking areas
        for area in trackingAreas {
            removeTrackingArea(area)
        }
        // Add fresh tracking area covering entire view
        let area = NSTrackingArea(
            rect: bounds,
            options: [.mouseMoved, .activeInKeyWindow, .inVisibleRect],
            owner: self,
            userInfo: nil
        )
        addTrackingArea(area)
    }

    override func mouseMoved(with event: NSEvent) {
        let location = convert(event.locationInWindow, from: nil)
        coordinator?.handleMouseMoved(at: location)
    }
}
