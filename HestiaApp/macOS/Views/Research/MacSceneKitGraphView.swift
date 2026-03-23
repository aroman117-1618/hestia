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
/// - Per-nodeType shapes (sphere, cube, octahedron, torus, capsule, ring)
/// - Per-edgeType styling (color, width, opacity)
struct MacSceneKitGraphView: NSViewRepresentable {
    let nodes: [MacNeuralNetViewModel.GraphNode]
    let edges: [MacNeuralNetViewModel.GraphEdge]
    @Binding var selectedNode: MacNeuralNetViewModel.GraphNode?
    @Binding var hoveredNode: MacNeuralNetViewModel.GraphNode?

    func makeNSView(context: Context) -> HoverableSCNView {
        let sceneView = HoverableSCNView()
        sceneView.backgroundColor = .clear
        sceneView.wantsLayer = true
        sceneView.layer?.isOpaque = false
        sceneView.layer?.backgroundColor = NSColor.clear.cgColor
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
        cameraNode.camera?.zFar = 200
        cameraNode.camera?.fieldOfView = 50
        cameraNode.position = SCNVector3(0, 0, 20)
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
            let edgeNode = createEdgeNode(from: fromPos, to: toPos, edge: edge)
            scene.rootNode.addChildNode(edgeNode)
        }

        // Nodes — shape varies by nodeType
        for node in nodes {
            let sceneNode = createNodeGeometry(for: node)
            scene.rootNode.addChildNode(sceneNode)
        }

        return scene
    }

    // MARK: - Node Geometry (shape per nodeType)

    private func createNodeGeometry(for graphNode: MacNeuralNetViewModel.GraphNode) -> SCNNode {
        let r = CGFloat(graphNode.radius)
        let geometry: SCNGeometry

        switch graphNode.nodeType {
        case "topic":
            // Diamond / octahedron — using a low-segment sphere approximation
            let sphere = SCNSphere(radius: r)
            sphere.segmentCount = 4  // creates a diamond-like shape
            geometry = sphere

        case "entity":
            // Shape varies by entity sub-type (category field)
            switch graphNode.category {
            case "person":
                let sphere = SCNSphere(radius: r)
                sphere.segmentCount = 24
                geometry = sphere
            case "tool":
                let side = r * 1.6
                geometry = SCNBox(width: side, height: side, length: side, chamferRadius: side * 0.1)
            case "project":
                geometry = SCNCapsule(capRadius: r * 0.6, height: r * 2.2)
            case "organization":
                let side = r * 1.6
                geometry = SCNBox(width: side, height: side, length: side, chamferRadius: side * 0.3)
            case "place":
                geometry = SCNCylinder(radius: r * 0.9, height: r * 1.2)
            default: // concept and unknown
                let sphere = SCNSphere(radius: r)
                sphere.segmentCount = 4  // diamond-like
                geometry = sphere
            }

        case "principle":
            // Torus — distinctive ring shape
            geometry = SCNTorus(ringRadius: r * 1.0, pipeRadius: r * 0.35)

        case "community":
            // Large translucent sphere — bigger than other nodes
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
            return node  // skip standard material — custom translucent

        case "episode":
            // Capsule / pill shape — elongated
            geometry = SCNCapsule(capRadius: r * 0.6, height: r * 2.5)

        case "fact":
            // Small cylinder / disk
            geometry = SCNCylinder(radius: r * 0.8, height: r * 0.4)

        default:
            // Memory nodes: standard sphere
            let sphere = SCNSphere(radius: r)
            sphere.segmentCount = 24
            geometry = sphere
        }

        // Sprint 20A: Visual weight system
        // Opacity maps to confidence (0.3–1.0) — low-confidence nodes fade
        let confidenceAlpha = CGFloat(0.3 + graphNode.confidence * 0.7)
        // Glow maps to recency — recent nodes glow brighter
        let recencyGlow: CGFloat
        if let lastActive = graphNode.lastActive {
            let ageDays = -lastActive.timeIntervalSinceNow / 86400.0
            recencyGlow = CGFloat(max(0.1, min(0.8, 0.8 - ageDays / 90.0 * 0.7)))
        } else {
            recencyGlow = 0.3 // default for nodes without date
        }

        let material = SCNMaterial()
        material.diffuse.contents = graphNode.color.withAlphaComponent(confidenceAlpha)
        material.emission.contents = graphNode.color.withAlphaComponent(recencyGlow)
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

        // Subtle pulse animation
        let pulse = SCNAction.sequence([
            SCNAction.scale(to: 1.05, duration: 1.5),
            SCNAction.scale(to: 0.95, duration: 1.5)
        ])
        node.runAction(SCNAction.repeatForever(pulse))

        return node
    }

    private func addBillboardLabel(to node: SCNNode, graphNode: MacNeuralNetViewModel.GraphNode) {
        let labelStr = String(graphNode.label.prefix(25))
        guard !labelStr.isEmpty else { return }

        let labelText = SCNText(string: labelStr, extrusionDepth: 0.005)
        labelText.font = NSFont.systemFont(ofSize: 0.12, weight: .medium)
        labelText.flatness = 0.3
        let labelMaterial = SCNMaterial()
        labelMaterial.diffuse.contents = NSColor(white: 0.92, alpha: 0.9)
        labelMaterial.lightingModel = .constant
        labelText.materials = [labelMaterial]

        let labelNode = SCNNode(geometry: labelText)
        let (minBound, maxBound) = labelNode.boundingBox
        let textWidth = CGFloat(maxBound.x) - CGFloat(minBound.x)
        labelNode.position = SCNVector3(
            -textWidth / 2,
            CGFloat(graphNode.radius) + 0.1,
            0
        )
        labelNode.scale = SCNVector3(1, 1, 0.1)

        let billboard = SCNBillboardConstraint()
        billboard.freeAxes = .all
        labelNode.constraints = [billboard]

        node.addChildNode(labelNode)
    }

    // MARK: - Edge Creation (styled by edgeType)

    private func createEdgeNode(from: SIMD3<Float>, to: SIMD3<Float>, edge: MacNeuralNetViewModel.GraphEdge) -> SCNNode {
        let delta = to - from
        let distance = simd_length(delta)
        guard distance > 0.01 else { return SCNNode() }

        // Edge styling varies by type
        let styling = edgeStyling(for: edge.edgeType, weight: edge.weight)

        let cylinder = SCNCylinder(radius: CGFloat(styling.radius), height: CGFloat(distance))
        let material = SCNMaterial()
        material.diffuse.contents = styling.color
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

    /// Returns (radius, color) for a given edge type.
    private func edgeStyling(for edgeType: String, weight: Float) -> (radius: Float, color: NSColor) {
        switch edgeType {
        case "relationship":
            // Entity-to-entity fact relationship: solid, thick, warm
            let r = 0.012 + weight * 0.015
            return (r, NSColor(red: 1.0, green: 0.6, blue: 0.2, alpha: CGFloat(0.15 + weight * 0.25)))

        case "supersedes":
            // Superseded fact: red tint, medium
            return (0.012, NSColor(red: 1.0, green: 0.2, blue: 0.2, alpha: 0.3))

        case "principle_source":
            // Principle to source chunk: purple, medium
            return (0.010, NSColor(red: 0.75, green: 0.35, blue: 0.95, alpha: 0.25))

        case "community_member":
            // Entity to community: thin, subtle
            return (0.005, NSColor(red: 1.0, green: 0.2, blue: 0.37, alpha: 0.15))

        case "topic_membership":
            // Memory to topic: thin, yellow tint
            return (0.005, NSColor(red: 1.0, green: 0.84, blue: 0.04, alpha: 0.15))

        case "entity_membership":
            // Memory to entity: thin, green tint
            return (0.005, NSColor(red: 0.19, green: 0.82, blue: 0.35, alpha: 0.15))

        case "semantic":
            // Episode to entity or semantic link: medium, blue
            return (0.008, NSColor(red: 0.35, green: 0.78, blue: 0.98, alpha: 0.20))

        default:
            // shared_topic / shared_entity: original white styling
            let r = 0.008 + weight * 0.012
            return (r, NSColor.white.withAlphaComponent(CGFloat(0.08 + weight * 0.15)))
        }
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
