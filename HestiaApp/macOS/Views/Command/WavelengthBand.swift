import SwiftUI

/// Decorative amber wavelength animation for the Command hero section.
/// Uses TimelineView for smooth continuous animation.
struct WavelengthBand: View {
    var body: some View {
        TimelineView(.animation) { timeline in
            let elapsed = timeline.date.timeIntervalSinceReferenceDate
            let phase = elapsed.truncatingRemainder(dividingBy: 4.0) / 4.0

            Canvas { context, size in
                let midY = size.height / 2
                let amplitude: CGFloat = 8
                let wavelength: CGFloat = 40

                // Primary wave
                var path1 = Path()
                path1.move(to: CGPoint(x: 0, y: midY))
                for x in stride(from: 0, through: size.width, by: 2) {
                    let y = midY + sin((x / wavelength + phase) * .pi * 2) * amplitude
                    path1.addLine(to: CGPoint(x: x, y: y))
                }
                context.stroke(
                    path1,
                    with: .linearGradient(
                        Gradient(colors: [
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(1),
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(0.5),
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(0)
                        ]),
                        startPoint: .zero,
                        endPoint: CGPoint(x: size.width, y: 0)
                    ),
                    lineWidth: 1.6
                )

                // Secondary wave (offset, fainter)
                var path2 = Path()
                path2.move(to: CGPoint(x: 0, y: midY + 4))
                for x in stride(from: 0, through: size.width, by: 2) {
                    let y = midY + 4 + sin((x / wavelength + phase + 0.3) * .pi * 2) * (amplitude * 0.6)
                    path2.addLine(to: CGPoint(x: x, y: y))
                }
                context.stroke(
                    path2,
                    with: .linearGradient(
                        Gradient(colors: [
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(0.3),
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(0.15),
                            Color(red: 1, green: 0.624, blue: 0.039).opacity(0)
                        ]),
                        startPoint: .zero,
                        endPoint: CGPoint(x: size.width, y: 0)
                    ),
                    lineWidth: 1.0
                )
            }
        }
        .frame(width: 260, height: 22)
    }
}
