import SwiftUI
import HestiaShared

/// Dark-to-amber atmospheric gradient for onboarding screens.
/// Static (no animation) — all motion is concentrated in the orb.
struct OnboardingBackground: View {
    var body: some View {
        GeometryReader { geo in
            ZStack {
                // 12-stop linear gradient: near-black → warm dark → deep amber
                LinearGradient(
                    stops: [
                        .init(color: Color(hex: "080503"), location: 0.0),
                        .init(color: Color(hex: "0A0704"), location: 0.10),
                        .init(color: Color(hex: "0D0802"), location: 0.22),
                        .init(color: Color(hex: "100A03"), location: 0.35),
                        .init(color: Color(hex: "130C04"), location: 0.48),
                        .init(color: Color(hex: "170F05"), location: 0.58),
                        .init(color: Color(hex: "1A1005"), location: 0.68),
                        .init(color: Color(hex: "1E1308"), location: 0.76),
                        .init(color: Color(hex: "23170A"), location: 0.83),
                        .init(color: Color(hex: "281A0C"), location: 0.89),
                        .init(color: Color(hex: "2D1E0F"), location: 0.94),
                        .init(color: Color(hex: "332211"), location: 1.0),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )

                // Atmospheric radial glow at bottom center
                RadialGradient(
                    colors: [
                        Color(hex: "FF9F0A").opacity(0.12),
                        Color(hex: "B36B07").opacity(0.06),
                        Color.clear,
                    ],
                    center: UnitPoint(x: 0.5, y: 1.3),
                    startRadius: 0,
                    endRadius: geo.size.height * 0.5
                )
            }
        }
        .ignoresSafeArea()
    }
}

struct OnboardingBackground_Previews: PreviewProvider {
    static var previews: some View {
        OnboardingBackground()
    }
}
