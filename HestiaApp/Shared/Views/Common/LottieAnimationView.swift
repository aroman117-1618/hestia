import SwiftUI
import Lottie

/// Reusable Lottie animation wrapper with accessibility support
///
/// Automatically falls back to a static SF Symbol when Reduce Motion is enabled.
/// Supports runtime color overrides via `colorOverrides` parameter.
struct HestiaLottieView: UIViewRepresentable {
    let animationName: String
    var loopMode: LottieLoopMode = .loop
    var speed: CGFloat = 1.0
    var contentMode: UIView.ContentMode = .scaleAspectFit
    /// Optional color overrides: [(keypath pattern, color)]
    var colorOverrides: [(String, Color)] = []

    func makeUIView(context: Context) -> LottieAnimationViewBase {
        let animationView = LottieAnimationView(name: animationName)
        animationView.loopMode = loopMode
        animationView.animationSpeed = speed
        animationView.contentMode = contentMode
        animationView.backgroundBehavior = .pauseAndRestore

        // Apply color overrides
        for (keypath, color) in colorOverrides {
            let uiColor = UIColor(color)
            var red: CGFloat = 0, green: CGFloat = 0, blue: CGFloat = 0, alpha: CGFloat = 0
            uiColor.getRed(&red, green: &green, blue: &blue, alpha: &alpha)
            animationView.setValueProvider(
                ColorValueProvider(LottieColor(r: Double(red), g: Double(green), b: Double(blue), a: Double(alpha))),
                keypath: AnimationKeypath(keypath: keypath)
            )
        }

        animationView.play()

        // Auto Layout constraints
        animationView.translatesAutoresizingMaskIntoConstraints = false
        return animationView
    }

    func updateUIView(_ uiView: LottieAnimationViewBase, context: Context) {
        // No dynamic updates needed — animation plays on create
    }
}

/// SwiftUI wrapper that handles accessibility Reduce Motion fallback
struct LottieView: View {
    let animationName: String
    var loopMode: LottieLoopMode = .loop
    var speed: CGFloat = 1.0
    var contentMode: UIView.ContentMode = .scaleAspectFit
    var colorOverrides: [(String, Color)] = []
    /// SF Symbol name to show when Reduce Motion is enabled
    var fallbackSymbol: String = "brain"
    var fallbackColor: Color = .white

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if reduceMotion {
            Image(systemName: fallbackSymbol)
                .font(.system(size: 48))
                .foregroundColor(fallbackColor)
        } else {
            HestiaLottieView(
                animationName: animationName,
                loopMode: loopMode,
                speed: speed,
                contentMode: contentMode,
                colorOverrides: colorOverrides
            )
        }
    }
}

// MARK: - Preview

struct LottieView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: Spacing.xl) {
                // AI Blob
                LottieView(
                    animationName: "ai_blob",
                    fallbackSymbol: "brain.head.profile"
                )
                .frame(width: 200, height: 200)

                // Typing indicator
                LottieView(
                    animationName: "typing_indicator",
                    colorOverrides: [
                        ("**.Fill 1.Color", .white.opacity(0.7))
                    ],
                    fallbackSymbol: "ellipsis"
                )
                .frame(width: 60, height: 40)
            }
        }
    }
}
