import SwiftUI
import HestiaShared

/// Dark-to-teal atmospheric gradient for onboarding screens.
/// Static (no animation) — all motion is concentrated in the orb.
struct OnboardingBackground: View {
    var body: some View {
        GeometryReader { geo in
            ZStack {
                // 12-stop linear gradient: near-black → warm dark → deep teal
                LinearGradient(
                    stops: [
                        .init(color: Color(hex: "050404"), location: 0.0),
                        .init(color: Color(hex: "0A0806"), location: 0.10),
                        .init(color: Color(hex: "0D0A07"), location: 0.22),
                        .init(color: Color(hex: "0C0B09"), location: 0.35),
                        .init(color: Color(hex: "0A0C0A"), location: 0.48),
                        .init(color: Color(hex: "0A100E"), location: 0.58),
                        .init(color: Color(hex: "0C1A16"), location: 0.68),
                        .init(color: Color(hex: "10251F"), location: 0.76),
                        .init(color: Color(hex: "153028"), location: 0.83),
                        .init(color: Color(hex: "1A3B32"), location: 0.89),
                        .init(color: Color(hex: "1F453B"), location: 0.94),
                        .init(color: Color(hex: "245044"), location: 1.0),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )

                // Atmospheric radial glow at bottom center
                RadialGradient(
                    colors: [
                        Color(hex: "2A7A6A").opacity(0.18),
                        Color(hex: "235A4C").opacity(0.10),
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
