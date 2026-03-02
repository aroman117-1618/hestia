import SwiftUI

enum DiagramEdgeStyle {
    case arrow
    case dashed
    case bidirectional
}

struct DiagramEdgeView: View {
    let from: CGPoint
    let to: CGPoint
    var label: String? = nil
    var style: DiagramEdgeStyle = .arrow
    var color: Color = MacColors.amberAccent.opacity(0.6)

    var body: some View {
        ZStack {
            edgePath
                .stroke(color, style: strokeStyle)

            if style == .arrow || style == .bidirectional {
                arrowHead(at: to, from: from)
            }
            if style == .bidirectional {
                arrowHead(at: from, from: to)
            }

            if let label = label {
                Text(label)
                    .font(.system(size: 9))
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 1)
                    .background(MacColors.panelBackground.opacity(0.9))
                    .position(midpoint)
            }
        }
    }

    private var edgePath: Path {
        Path { path in
            path.move(to: from)
            path.addLine(to: to)
        }
    }

    private var strokeStyle: StrokeStyle {
        switch style {
        case .dashed:
            return StrokeStyle(lineWidth: 1.5, dash: [4, 3])
        case .arrow, .bidirectional:
            return StrokeStyle(lineWidth: 1.5)
        }
    }

    private var midpoint: CGPoint {
        CGPoint(x: (from.x + to.x) / 2, y: (from.y + to.y) / 2)
    }

    private func arrowHead(at tip: CGPoint, from origin: CGPoint) -> some View {
        let angle = atan2(tip.y - origin.y, tip.x - origin.x)
        let arrowLength: CGFloat = 8
        let arrowAngle: CGFloat = .pi / 6

        let p1 = CGPoint(
            x: tip.x - arrowLength * cos(angle - arrowAngle),
            y: tip.y - arrowLength * sin(angle - arrowAngle)
        )
        let p2 = CGPoint(
            x: tip.x - arrowLength * cos(angle + arrowAngle),
            y: tip.y - arrowLength * sin(angle + arrowAngle)
        )

        return Path { path in
            path.move(to: tip)
            path.addLine(to: p1)
            path.move(to: tip)
            path.addLine(to: p2)
        }
        .stroke(color, lineWidth: 1.5)
    }
}
