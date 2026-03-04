import SwiftUI

struct IntegrationMapDiagramView: View {
    private struct SpokeData: Identifiable {
        let id: Int
        let icon: String
        let label: String
        let sublabel: String
        let accentColor: Color
    }

    private let spokes: [SpokeData] = [
        SpokeData(id: 0, icon: "apple.logo", label: "Apple", sublabel: "20 tools", accentColor: MacColors.diagramApple),
        SpokeData(id: 1, icon: "heart.fill", label: "HealthKit", sublabel: "28 metrics", accentColor: MacColors.healthRed),
        SpokeData(id: 2, icon: "folder.badge.gearshape", label: "Explorer", sublabel: "Files", accentColor: MacColors.amberAccent),
        SpokeData(id: 3, icon: "newspaper", label: "Newsfeed", sublabel: "Sources", accentColor: MacColors.amberAccent),
        SpokeData(id: 4, icon: "magnifyingglass", label: "Investigate", sublabel: "URLs", accentColor: MacColors.amberAccent),
    ]

    var body: some View {
        DiagramContainerView(title: "Integration Map", subtitle: "External connections") {
            GeometryReader { geo in
                let w = geo.size.width
                let h = max(geo.size.height, 260)
                let cx = w / 2
                let cy = h / 2 - 10
                let radius: CGFloat = min(w, h) * 0.32

                ZStack {
                    // Decorative ring
                    Circle()
                        .strokeBorder(MacColors.amberAccent.opacity(0.1), lineWidth: 1)
                        .frame(width: radius * 1.3, height: radius * 1.3)
                        .position(x: cx, y: cy)

                    // Hub (center)
                    DiagramNodeView(icon: "flame", label: "Hestia", sublabel: "Hub", width: 90)
                        .position(x: cx, y: cy)

                    // Spokes
                    ForEach(spokes) { spoke in
                        spokeView(spoke, center: CGPoint(x: cx, y: cy), radius: radius)
                    }

                    // Legend
                    DiagramLegendView(items: [
                        DiagramLegendItem(color: MacColors.diagramApple, label: "Apple"),
                        DiagramLegendItem(color: MacColors.healthRed, label: "Health"),
                        DiagramLegendItem(color: MacColors.amberAccent, label: "Hestia Modules"),
                    ])
                    .position(x: cx, y: h - 5)
                }
                .frame(width: w, height: h)
            }
            .frame(minHeight: 260)
        }
    }

    private func spokePosition(for spoke: SpokeData, center: CGPoint, radius: CGFloat) -> CGPoint {
        let angle: Double = (2 * .pi / Double(spokes.count)) * Double(spoke.id) - .pi / 2
        let x: CGFloat = center.x + radius * cos(angle)
        let y: CGFloat = center.y + radius * sin(angle)
        return CGPoint(x: x, y: y)
    }

    private func edgePoints(for spoke: SpokeData, center: CGPoint, radius: CGFloat) -> (from: CGPoint, to: CGPoint) {
        let angle: Double = (2 * .pi / Double(spokes.count)) * Double(spoke.id) - .pi / 2
        let cosA: CGFloat = cos(angle)
        let sinA: CGFloat = sin(angle)
        let innerRadius: CGFloat = 45
        let outerStart: CGFloat = radius - 45
        let fromPt = CGPoint(x: center.x + innerRadius * cosA, y: center.y + innerRadius * sinA)
        let toPt = CGPoint(x: center.x + outerStart * cosA, y: center.y + outerStart * sinA)
        return (fromPt, toPt)
    }

    @ViewBuilder
    private func spokeView(_ spoke: SpokeData, center: CGPoint, radius: CGFloat) -> some View {
        let pos = spokePosition(for: spoke, center: center, radius: radius)
        let edge = edgePoints(for: spoke, center: center, radius: radius)

        DiagramNodeView(
            icon: spoke.icon,
            label: spoke.label,
            sublabel: spoke.sublabel,
            accentColor: spoke.accentColor,
            width: 90
        )
        .position(x: pos.x, y: pos.y)

        DiagramEdgeView(from: edge.from, to: edge.to, style: .bidirectional)
    }
}
