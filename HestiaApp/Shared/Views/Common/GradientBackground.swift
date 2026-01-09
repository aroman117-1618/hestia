import SwiftUI

/// Animated gradient background that changes with mode
/// Animation pauses when app is backgrounded to save battery
struct GradientBackground: View {
    let mode: HestiaMode
    @State private var animateGradient = false
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        LinearGradient(
            colors: mode.gradientColors,
            startPoint: animateGradient ? .topLeading : .top,
            endPoint: animateGradient ? .bottomTrailing : .bottom
        )
        .ignoresSafeArea()
        .animation(.easeInOut(duration: 3).repeatForever(autoreverses: true), value: animateGradient)
        .onAppear {
            animateGradient = true
        }
        .onChange(of: scenePhase) { phase in
            // Pause animation when app is not active to save battery
            animateGradient = (phase == .active)
        }
        .id(mode) // Force recreation on mode change
        .transition(.opacity)
    }
}

/// Static gradient background (no animation)
struct StaticGradientBackground: View {
    let mode: HestiaMode

    var body: some View {
        mode.gradient
            .ignoresSafeArea()
    }
}

/// Gradient background with mesh effect (iOS 16+)
struct MeshGradientBackground: View {
    let mode: HestiaMode
    @State private var phase: CGFloat = 0

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let colors = mode.gradientColors

                // Create a gradient with shifting positions
                let gradient = Gradient(colors: colors)
                let rect = CGRect(origin: .zero, size: size)

                // Animate the gradient angle
                let time = timeline.date.timeIntervalSinceReferenceDate
                let angle = Angle.degrees(sin(time * 0.3) * 30)

                context.fill(
                    Path(rect),
                    with: .linearGradient(
                        gradient,
                        startPoint: CGPoint(
                            x: size.width * 0.5 + cos(angle.radians) * size.width * 0.5,
                            y: 0
                        ),
                        endPoint: CGPoint(
                            x: size.width * 0.5 - cos(angle.radians) * size.width * 0.5,
                            y: size.height
                        )
                    )
                )
            }
        }
        .ignoresSafeArea()
    }
}

// MARK: - Gradient Overlay

/// Overlay gradient for cards and content areas
struct GradientOverlay: View {
    let opacity: Double

    init(opacity: Double = 0.3) {
        self.opacity = opacity
    }

    var body: some View {
        LinearGradient(
            colors: [
                Color.black.opacity(0),
                Color.black.opacity(opacity)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
    }
}

// MARK: - Preview

struct GradientBackground_Previews: PreviewProvider {
    struct PreviewWrapper: View {
        @State var mode: HestiaMode = .tia

        var body: some View {
            ZStack {
                GradientBackground(mode: mode)

                VStack {
                    Text("Mode: \(mode.displayName)")
                        .font(.title)
                        .foregroundColor(.white)

                    HStack(spacing: 20) {
                        ForEach(HestiaMode.allCases) { m in
                            Button(m.displayName) {
                                withAnimation(.modeSwitch) {
                                    mode = m
                                }
                            }
                            .foregroundColor(.white)
                            .padding()
                            .background(Color.white.opacity(0.2))
                            .cornerRadius(10)
                        }
                    }
                }
            }
        }
    }

    static var previews: some View {
        PreviewWrapper()
    }
}
