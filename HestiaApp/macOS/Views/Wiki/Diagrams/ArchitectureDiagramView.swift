import SwiftUI

struct ArchitectureDiagramView: View {
    var body: some View {
        DiagramContainerView(title: "System Architecture", subtitle: "How the layers connect") {
            GeometryReader { geo in
                let w = geo.size.width
                let h = max(geo.size.height, 320)
                let cx = w / 2

                ZStack {
                    // Layer 1: iOS App (top)
                    DiagramNodeView(icon: "iphone", label: "iOS App", sublabel: "SwiftUI", accentColor: MacColors.diagramExternal, width: 100)
                        .position(x: cx, y: 30)

                    // Layer 2: API
                    DiagramNodeView(icon: "network", label: "API Layer", sublabel: "FastAPI + JWT", width: 110)
                        .position(x: cx, y: 90)

                    // Layer 3: Processing (horizontal spread)
                    DiagramNodeView(icon: "gearshape.2", label: "Orchestration", width: 100)
                        .position(x: cx - 130, y: 160)
                    DiagramNodeView(icon: "brain", label: "Memory", width: 80)
                        .position(x: cx - 30, y: 160)
                    DiagramNodeView(icon: "cpu", label: "Inference", width: 80)
                        .position(x: cx + 60, y: 160)
                    DiagramNodeView(icon: "terminal", label: "Execution", width: 80)
                        .position(x: cx + 150, y: 160)

                    // Layer 4: Storage/External (bottom)
                    DiagramNodeView(icon: "cylinder", label: "Ollama", sublabel: "Local LLM", accentColor: MacColors.healthGreen, width: 90)
                        .position(x: cx - 150, y: 240)
                    DiagramNodeView(icon: "cylinder.split.1x2", label: "ChromaDB", sublabel: "Vectors", accentColor: MacColors.healthGreen, width: 90)
                        .position(x: cx - 50, y: 240)
                    DiagramNodeView(icon: "tablecells", label: "SQLite", sublabel: "Structured", accentColor: MacColors.healthGreen, width: 80)
                        .position(x: cx + 45, y: 240)
                    DiagramNodeView(icon: "apple.logo", label: "Apple Tools", sublabel: "20 tools", accentColor: MacColors.diagramApple, width: 90)
                        .position(x: cx + 140, y: 240)

                    // Cloud providers (far right)
                    DiagramNodeView(icon: "cloud", label: "Cloud LLMs", sublabel: "3 providers", accentColor: MacColors.diagramCloud, width: 90)
                        .position(x: min(w - 50, cx + 220), y: 160)

                    // Security border overlay
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(MacColors.healthGreen.opacity(0.2), style: StrokeStyle(lineWidth: 1, dash: [6, 4]))
                        .frame(width: w - 40, height: 180)
                        .position(x: cx, y: 190)

                    Text("Security Layer")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundStyle(MacColors.healthGreen.opacity(0.5))
                        .position(x: 60, y: 105)

                    // Arrows (simplified vertical connections)
                    DiagramEdgeView(
                        from: CGPoint(x: cx, y: 54),
                        to: CGPoint(x: cx, y: 68)
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx - 50, y: 112),
                        to: CGPoint(x: cx - 130, y: 135)
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx - 10, y: 112),
                        to: CGPoint(x: cx - 30, y: 135)
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx + 20, y: 112),
                        to: CGPoint(x: cx + 60, y: 135)
                    )
                    DiagramEdgeView(
                        from: CGPoint(x: cx + 50, y: 112),
                        to: CGPoint(x: cx + 150, y: 135)
                    )

                    // Legend
                    DiagramLegendView(items: [
                        DiagramLegendItem(color: MacColors.healthGreen, label: "Storage"),
                        DiagramLegendItem(color: MacColors.amberAccent, label: "Processing"),
                        DiagramLegendItem(color: MacColors.diagramExternal, label: "External"),
                    ])
                    .position(x: cx, y: h - 15)
                }
                .frame(width: w, height: h)
            }
            .frame(minHeight: 320)
        }
    }
}
