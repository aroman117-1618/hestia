import SwiftUI

struct RequestLifecycleDiagramView: View {
    var body: some View {
        DiagramContainerView(title: "Request Lifecycle", subtitle: "A chat message's journey") {
            GeometryReader { geo in
                let w = geo.size.width
                let h = max(geo.size.height, 260)
                let stepW = max(80, (w - 60) / 6)
                let startX: CGFloat = 30 + stepW / 2
                let y: CGFloat = h / 2 - 20

                ZStack {
                    // Main pipeline (left to right)
                    DiagramNodeView(icon: "iphone", label: "iOS", accentColor: .blue, width: stepW * 0.9)
                        .position(x: startX, y: y)

                    DiagramNodeView(icon: "lock.shield", label: "Auth", sublabel: "JWT", accentColor: MacColors.healthGreen, width: stepW * 0.9)
                        .position(x: startX + stepW, y: y)

                    DiagramNodeView(icon: "gearshape.2", label: "Handler", sublabel: "State Machine", width: stepW * 0.9)
                        .position(x: startX + stepW * 2, y: y)

                    DiagramNodeView(icon: "person.3", label: "Council", sublabel: "SLM Intent", width: stepW * 0.9)
                        .position(x: startX + stepW * 3, y: y)

                    DiagramNodeView(icon: "cpu", label: "Inference", sublabel: "Ollama/Cloud", width: stepW * 0.9)
                        .position(x: startX + stepW * 4, y: y)

                    DiagramNodeView(icon: "arrow.left", label: "Response", accentColor: MacColors.healthGreen, width: stepW * 0.9)
                        .position(x: startX + stepW * 5, y: y)

                    // Branch: Tool execution (below)
                    DiagramNodeView(icon: "terminal", label: "Tools", sublabel: "Sandbox", width: stepW * 0.8)
                        .position(x: startX + stepW * 3.5, y: y + 70)

                    // Branch: Memory (above)
                    DiagramNodeView(icon: "brain", label: "Memory", sublabel: "Search", width: stepW * 0.8)
                        .position(x: startX + stepW * 2.5, y: y - 65)

                    // Horizontal arrows
                    let nodeHW = stepW * 0.45
                    ForEach(0..<5, id: \.self) { i in
                        DiagramEdgeView(
                            from: CGPoint(x: startX + stepW * CGFloat(i) + nodeHW, y: y),
                            to: CGPoint(x: startX + stepW * CGFloat(i + 1) - nodeHW, y: y)
                        )
                    }

                    // Branch arrows (tool fork)
                    DiagramEdgeView(
                        from: CGPoint(x: startX + stepW * 3.5, y: y + 25),
                        to: CGPoint(x: startX + stepW * 3.5, y: y + 45),
                        label: "tool call?",
                        style: .dashed
                    )

                    // Branch arrows (memory fork)
                    DiagramEdgeView(
                        from: CGPoint(x: startX + stepW * 2.5, y: y - 25),
                        to: CGPoint(x: startX + stepW * 2.5, y: y - 40),
                        label: "context",
                        style: .dashed
                    )

                    // Legend
                    DiagramLegendView(items: [
                        DiagramLegendItem(color: MacColors.amberAccent, label: "Core Pipeline"),
                        DiagramLegendItem(color: MacColors.healthGreen, label: "Auth/Response"),
                        DiagramLegendItem(color: .blue, label: "Client"),
                    ])
                    .position(x: w / 2, y: h - 10)
                }
                .frame(width: w, height: h)
            }
            .frame(minHeight: 260)
        }
    }
}
