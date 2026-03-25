import SwiftUI

struct DataFlowDiagramView: View {
    var body: some View {
        DiagramContainerView(title: "Data Flow", subtitle: "Where data lives and moves") {
            GeometryReader { geo in
                let w = geo.size.width
                let h = max(geo.size.height, 260)
                let pipeY: CGFloat = 60
                let stepW = max(80, (w - 40) / 6)
                let startX: CGFloat = 20 + stepW / 2

                ZStack {
                    pipelineNodes(startX: startX, stepW: stepW, pipeY: pipeY)
                    storageNodes(w: w, h: h)
                    pipelineArrows(startX: startX, stepW: stepW, pipeY: pipeY)
                    loopArrow(startX: startX, stepW: stepW, pipeY: pipeY, storageY: h - 50, w: w)
                    storageConnections(startX: startX, stepW: stepW, pipeY: pipeY, storageY: h - 50, w: w)

                    DiagramLegendView(items: [
                        DiagramLegendItem(color: MacColors.amberAccent, label: "Pipeline"),
                        DiagramLegendItem(color: MacColors.healthGreen, label: "Storage"),
                    ])
                    .position(x: w / 2, y: h - 5)
                }
                .frame(width: w, height: h)
            }
            .frame(minHeight: 260)
        }
    }

    // MARK: - Pipeline (top row)

    @ViewBuilder
    private func pipelineNodes(startX: CGFloat, stepW: CGFloat, pipeY: CGFloat) -> some View {
        let nodeW = stepW * 0.85
        DiagramNodeView(icon: "text.bubble", label: "User Input", width: nodeW)
            .position(x: startX, y: pipeY)
        DiagramNodeView(icon: "brain", label: "Memory", sublabel: "Search", width: nodeW)
            .position(x: startX + stepW, y: pipeY)
        DiagramNodeView(icon: "doc.text", label: "Context", sublabel: "Assembly", width: nodeW)
            .position(x: startX + stepW * 2, y: pipeY)
        DiagramNodeView(icon: "cpu", label: "Inference", width: nodeW)
            .position(x: startX + stepW * 3, y: pipeY)
        DiagramNodeView(icon: "wrench", label: "Tool Detect", width: nodeW)
            .position(x: startX + stepW * 4, y: pipeY)
        DiagramNodeView(icon: "tray.and.arrow.up", label: "Staging", sublabel: "Auto-persist", width: nodeW)
            .position(x: startX + stepW * 5, y: pipeY)
    }

    // MARK: - Storage (bottom row)

    @ViewBuilder
    private func storageNodes(w: CGFloat, h: CGFloat) -> some View {
        let storageY = h - 50
        DiagramNodeView(icon: "cylinder.split.1x2", label: "ChromaDB", sublabel: "Vectors", accentColor: MacColors.healthGreen, width: 90)
            .position(x: w * 0.2, y: storageY)
        DiagramNodeView(icon: "tablecells", label: "SQLite", sublabel: "Structured", accentColor: MacColors.healthGreen, width: 85)
            .position(x: w * 0.5, y: storageY)
        DiagramNodeView(icon: "lock.shield", label: "Keychain", sublabel: "Credentials", accentColor: MacColors.healthGreen, width: 90)
            .position(x: w * 0.8, y: storageY)
    }

    // MARK: - Arrows

    @ViewBuilder
    private func pipelineArrows(startX: CGFloat, stepW: CGFloat, pipeY: CGFloat) -> some View {
        let nodeHW = stepW * 0.43
        ForEach(0..<5, id: \.self) { i in
            DiagramEdgeView(
                from: CGPoint(x: startX + stepW * CGFloat(i) + nodeHW, y: pipeY),
                to: CGPoint(x: startX + stepW * CGFloat(i + 1) - nodeHW, y: pipeY)
            )
        }
    }

    @ViewBuilder
    private func loopArrow(startX: CGFloat, stepW: CGFloat, pipeY: CGFloat, storageY: CGFloat, w: CGFloat) -> some View {
        let sx = startX + stepW * 5
        let sy = pipeY + 30
        let ey = storageY - 30
        let targetX = w * 0.2

        Path { path in
            path.move(to: CGPoint(x: sx, y: sy))
            path.addCurve(
                to: CGPoint(x: targetX, y: ey),
                control1: CGPoint(x: sx + 30, y: (sy + ey) / 2),
                control2: CGPoint(x: targetX + 30, y: (sy + ey) / 2)
            )
        }
        .stroke(MacColors.amberAccent.opacity(0.4), style: StrokeStyle(lineWidth: 1.5, dash: [4, 3]))

        Text("persist")
            .font(MacTypography.micro)
            .foregroundStyle(MacColors.textFaint)
            .position(x: w * 0.85, y: (pipeY + storageY) / 2)
    }

    @ViewBuilder
    private func storageConnections(startX: CGFloat, stepW: CGFloat, pipeY: CGFloat, storageY: CGFloat, w: CGFloat) -> some View {
        let memoryX = startX + stepW
        DiagramEdgeView(
            from: CGPoint(x: memoryX, y: pipeY + 30),
            to: CGPoint(x: w * 0.2, y: storageY - 30),
            style: .dashed
        )
        DiagramEdgeView(
            from: CGPoint(x: memoryX, y: pipeY + 30),
            to: CGPoint(x: w * 0.5, y: storageY - 30),
            style: .dashed
        )
    }
}
