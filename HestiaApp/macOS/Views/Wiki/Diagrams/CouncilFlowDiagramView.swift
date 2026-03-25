import SwiftUI

struct CouncilFlowDiagramView: View {
    var body: some View {
        DiagramContainerView(title: "Council Decision Flow", subtitle: "Dual-path intent classification") {
            GeometryReader { geo in
                let w = geo.size.width
                let h = max(geo.size.height, 280)
                let cx = w / 2

                ZStack {
                    // Input
                    DiagramNodeView(icon: "text.bubble", label: "User Input", width: 100)
                        .position(x: cx, y: 30)

                    // SLM classification
                    DiagramNodeView(icon: "cpu", label: "SLM Intent", sublabel: "qwen2.5:0.5b", width: 110)
                        .position(x: cx, y: 95)

                    // Confidence gauge (simplified arc)
                    confidenceArc
                        .position(x: cx, y: 130)

                    // Fork: High confidence CHAT
                    DiagramNodeView(icon: "bolt", label: "Skip Council", sublabel: "CHAT > 0.8", accentColor: MacColors.healthGreen, width: 100)
                        .position(x: cx - 120, y: 170)

                    // Fork: Full council (4 roles)
                    let roleY: CGFloat = 200
                    DiagramNodeView(icon: "magnifyingglass", label: "Analyzer", width: 80)
                        .position(x: cx + 10, y: roleY)
                    DiagramNodeView(icon: "checkmark.shield", label: "Validator", width: 80)
                        .position(x: cx + 100, y: roleY)
                    DiagramNodeView(icon: "text.quote", label: "Responder", width: 80)
                        .position(x: cx + 10, y: roleY + 55)
                    DiagramNodeView(icon: "eye", label: "Sentinel", width: 80)
                        .position(x: cx + 100, y: roleY + 55)

                    // Parallel gather bracket
                    Path { path in
                        let left = cx - 28
                        let right = cx + 148
                        let top = roleY - 32
                        let bottom = roleY + 87
                        path.move(to: CGPoint(x: left, y: top))
                        path.addLine(to: CGPoint(x: left - 8, y: top))
                        path.addLine(to: CGPoint(x: left - 8, y: bottom))
                        path.addLine(to: CGPoint(x: left, y: bottom))
                        path.move(to: CGPoint(x: right, y: top))
                        path.addLine(to: CGPoint(x: right + 8, y: top))
                        path.addLine(to: CGPoint(x: right + 8, y: bottom))
                        path.addLine(to: CGPoint(x: right, y: bottom))
                    }
                    .stroke(MacColors.amberAccent.opacity(0.3), lineWidth: 1)

                    Text("asyncio.gather()")
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.textFaint)
                        .position(x: cx + 55, y: roleY - 40)

                    // Response
                    DiagramNodeView(icon: "arrow.left", label: "Response", accentColor: MacColors.healthGreen, width: 90)
                        .position(x: cx, y: h - 30)

                    // Arrows
                    DiagramEdgeView(from: CGPoint(x: cx, y: 55), to: CGPoint(x: cx, y: 72))
                    DiagramEdgeView(
                        from: CGPoint(x: cx - 40, y: 115),
                        to: CGPoint(x: cx - 120, y: 147),
                        label: "high conf",
                        style: .dashed
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx + 40, y: 115),
                        to: CGPoint(x: cx + 55, y: 165),
                        label: "other"
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx - 120, y: 193),
                        to: CGPoint(x: cx - 50, y: h - 40)
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx + 55, y: roleY + 80),
                        to: CGPoint(x: cx + 20, y: h - 43)
                    )

                    // Legend
                    DiagramLegendView(items: [
                        DiagramLegendItem(color: MacColors.amberAccent, label: "Processing"),
                        DiagramLegendItem(color: MacColors.healthGreen, label: "Fast Path"),
                    ])
                    .position(x: w / 2, y: h - 5)
                }
                .frame(width: w, height: h)
            }
            .frame(minHeight: 280)
        }
    }

    private var confidenceArc: some View {
        ZStack {
            // Background arc
            Circle()
                .trim(from: 0.25, to: 0.75)
                .stroke(MacColors.textFaint.opacity(0.2), lineWidth: 2)
                .frame(width: 30, height: 30)
                .rotationEffect(.degrees(0))

            // Filled arc (showing ~0.8 threshold)
            Circle()
                .trim(from: 0.25, to: 0.65)
                .stroke(MacColors.amberAccent.opacity(0.6), lineWidth: 2)
                .frame(width: 30, height: 30)
                .rotationEffect(.degrees(0))
        }
    }
}
