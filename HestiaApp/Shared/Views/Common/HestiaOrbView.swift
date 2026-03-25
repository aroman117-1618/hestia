import SwiftUI
import HestiaShared

// MARK: - Orb State

enum HestiaOrbState: Equatable {
    case idle
    case thinking
    case success
    case listening
}

// MARK: - HestiaOrbView

/// A fluid, luminous animated sphere rendered via SwiftUI Canvas.
///
/// Multiple layered organic noise circles create the illusion of
/// swirling plasma inside a glass sphere. The orb breathes, warps,
/// and pulses according to its current ``HestiaOrbState``.
struct HestiaOrbView: View {
    let state: HestiaOrbState
    var size: CGFloat = 150
    var audioLevel: CGFloat = 0.0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // MARK: - Color Palette

    private static let primaryAmber = Color(hex: "FF9F0A")
    private static let secondaryBrown = Color(hex: "B36B07")
    private static let highlightGold = Color(hex: "FFD080")
    private static let deepBrown = Color(hex: "7A4505")
    private static let coreWhite = Color(hex: "FFF0D0")

    // MARK: - Body

    var body: some View {
        if reduceMotion {
            staticFallback
        } else {
            animatedOrb
        }
    }

    // MARK: - Animated Orb

    private var animatedOrb: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, canvasSize in
                drawOrb(context: context, size: canvasSize, time: time)
            }
            .frame(width: size * 1.6, height: size * 1.6)
        }
    }

    // MARK: - Static Fallback

    private var staticFallback: some View {
        Circle()
            .fill(
                RadialGradient(
                    colors: [
                        Self.coreWhite,
                        Self.highlightGold,
                        Self.primaryAmber,
                        Self.secondaryBrown,
                        Self.deepBrown.opacity(0.3),
                    ],
                    center: UnitPoint(x: 0.35, y: 0.35),
                    startRadius: 0,
                    endRadius: size / 2
                )
            )
            .frame(width: size, height: size)
            .shadow(color: Self.primaryAmber.opacity(0.3), radius: 30)
    }

    // MARK: - Drawing

    private func drawOrb(context: GraphicsContext, size canvasSize: CGSize, time: Double) {
        let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
        let radius = self.size / 2

        let speed = animationSpeed
        let t = time * speed

        // Layer 1: Outer atmospheric glow (breathing)
        drawAtmosphericGlow(context: context, center: center, radius: radius, time: t)

        // Layer 2: Base sphere with gradient
        drawBaseSphere(context: context, center: center, radius: radius, time: t)

        // Layer 3-10: Organic fluid noise layers
        drawFluidLayers(context: context, center: center, radius: radius, time: t)

        // Layer 11: Inner specular highlight
        drawSpecularHighlight(context: context, center: center, radius: radius, time: t)

        // Layer 12: Fresnel rim lighting
        drawFresnelRim(context: context, center: center, radius: radius, time: t)
    }

    // MARK: - Atmospheric Glow

    private func drawAtmosphericGlow(
        context: GraphicsContext,
        center: CGPoint,
        radius: CGFloat,
        time: Double
    ) {
        let breathe = 1.0 + 0.08 * sin(time * 0.7)
        let glowRadius = radius * 1.5 * breathe
        let audioPulse = state == .listening ? (1.0 + audioLevel * 0.3) : 1.0

        let glowPath = Path(ellipseIn: CGRect(
            x: center.x - glowRadius * audioPulse,
            y: center.y - glowRadius * audioPulse,
            width: glowRadius * 2 * audioPulse,
            height: glowRadius * 2 * audioPulse
        ))

        let glowOpacity = state == .thinking ? 0.25 : 0.15
        context.fill(
            glowPath,
            with: .radialGradient(
                Gradient(colors: [
                    Self.primaryAmber.opacity(glowOpacity),
                    Self.secondaryBrown.opacity(glowOpacity * 0.4),
                    Color.clear,
                ]),
                center: center,
                startRadius: radius * 0.5,
                endRadius: glowRadius * audioPulse
            )
        )
    }

    // MARK: - Base Sphere

    private func drawBaseSphere(
        context: GraphicsContext,
        center: CGPoint,
        radius: CGFloat,
        time: Double
    ) {
        // Subtle shape distortion — warp the sphere outline
        let warpPath = warpedCirclePath(center: center, radius: radius, time: time, amplitude: 1.5)

        context.fill(
            warpPath,
            with: .radialGradient(
                Gradient(colors: [
                    Self.primaryAmber.opacity(0.9),
                    Self.secondaryBrown.opacity(0.95),
                    Self.deepBrown,
                ]),
                center: CGPoint(
                    x: center.x - radius * 0.15,
                    y: center.y - radius * 0.15
                ),
                startRadius: 0,
                endRadius: radius
            )
        )
    }

    // MARK: - Fluid Layers

    private func drawFluidLayers(
        context: GraphicsContext,
        center: CGPoint,
        radius: CGFloat,
        time: Double
    ) {
        // 8 organic noise layers at different depths
        let layerConfigs: [(phase: Double, speed: Double, scale: CGFloat, opacity: Double, color: Color)] = [
            // Deep background layers (large, slow, dark)
            (0.0, 0.3, 0.85, 0.15, Self.deepBrown),
            (1.2, 0.25, 0.78, 0.12, Self.secondaryBrown),
            // Mid layers (medium, moderate speed)
            (2.4, 0.5, 0.65, 0.18, Self.primaryAmber),
            (3.6, 0.45, 0.58, 0.14, Self.secondaryBrown.opacity(0.8)),
            (4.8, 0.55, 0.50, 0.20, Self.primaryAmber.opacity(0.7)),
            // Foreground wisps (small, faster, brighter)
            (6.0, 0.7, 0.38, 0.16, Self.highlightGold.opacity(0.6)),
            (7.2, 0.65, 0.30, 0.12, Self.coreWhite.opacity(0.3)),
            (8.4, 0.8, 0.25, 0.10, Self.highlightGold.opacity(0.4)),
        ]

        for (index, config) in layerConfigs.enumerated() {
            let i = Double(index)
            let layerTime = time * config.speed + config.phase

            // Each blob orbits on a different elliptical path
            let orbitX = sin(layerTime + i * 0.7) * radius * config.scale * 0.6
            let orbitY = cos(layerTime * 0.8 + i * 1.1) * radius * config.scale * 0.5

            let blobCenter = CGPoint(
                x: center.x + orbitX,
                y: center.y + orbitY
            )

            let blobRadius = radius * config.scale
            // Organic shape: stretched ellipse with rotation
            let stretchX = 1.0 + 0.3 * sin(layerTime * 1.3 + i)
            let stretchY = 1.0 + 0.3 * cos(layerTime * 1.1 + i * 0.5)
            let rotation = Angle.radians(layerTime * 0.4 + i * 0.9)

            let blobRect = CGRect(
                x: -blobRadius * stretchX,
                y: -blobRadius * stretchY,
                width: blobRadius * 2 * stretchX,
                height: blobRadius * 2 * stretchY
            )

            var blobContext = context
            blobContext.translateBy(x: blobCenter.x, y: blobCenter.y)
            blobContext.rotate(by: rotation)

            // Clip to sphere boundary
            let clipPath = Path(ellipseIn: CGRect(
                x: center.x - radius - blobCenter.x,
                y: center.y - radius - blobCenter.y,
                width: radius * 2,
                height: radius * 2
            ))
            blobContext.clip(to: clipPath)

            let blobPath = Path(ellipseIn: blobRect)

            let audioBrightness = state == .listening ? (1.0 + audioLevel * 0.5) : 1.0
            let thinkingBrightness = state == .thinking ? 1.3 : 1.0
            let adjustedOpacity = min(config.opacity * audioBrightness * thinkingBrightness, 0.5)

            blobContext.fill(
                blobPath,
                with: .radialGradient(
                    Gradient(colors: [
                        config.color.opacity(adjustedOpacity),
                        config.color.opacity(adjustedOpacity * 0.3),
                        Color.clear,
                    ]),
                    center: .zero,
                    startRadius: 0,
                    endRadius: blobRadius * max(stretchX, stretchY)
                )
            )
        }
    }

    // MARK: - Specular Highlight

    private func drawSpecularHighlight(
        context: GraphicsContext,
        center: CGPoint,
        radius: CGFloat,
        time: Double
    ) {
        // Drifting specular highlight (upper-left quadrant)
        let highlightDriftX = sin(time * 0.3) * radius * 0.12
        let highlightDriftY = cos(time * 0.25) * radius * 0.10

        let highlightCenter = CGPoint(
            x: center.x - radius * 0.28 + highlightDriftX,
            y: center.y - radius * 0.30 + highlightDriftY
        )

        let highlightRadius = radius * 0.35
        let highlightPath = Path(ellipseIn: CGRect(
            x: highlightCenter.x - highlightRadius,
            y: highlightCenter.y - highlightRadius * 0.7,
            width: highlightRadius * 2,
            height: highlightRadius * 1.4
        ))

        let highlightOpacity = state == .thinking ? 0.5 : 0.3

        // Clip to sphere
        var highlightContext = context
        let sphereClip = Path(ellipseIn: CGRect(
            x: center.x - radius,
            y: center.y - radius,
            width: radius * 2,
            height: radius * 2
        ))
        highlightContext.clip(to: sphereClip)

        highlightContext.fill(
            highlightPath,
            with: .radialGradient(
                Gradient(colors: [
                    Self.coreWhite.opacity(highlightOpacity),
                    Self.highlightGold.opacity(highlightOpacity * 0.4),
                    Color.clear,
                ]),
                center: highlightCenter,
                startRadius: 0,
                endRadius: highlightRadius
            )
        )

        // Secondary smaller highlight for glass realism
        let secondaryCenter = CGPoint(
            x: center.x - radius * 0.15 + highlightDriftX * 0.5,
            y: center.y - radius * 0.40 + highlightDriftY * 0.5
        )
        let secondaryRadius = radius * 0.12
        let secondaryPath = Path(ellipseIn: CGRect(
            x: secondaryCenter.x - secondaryRadius,
            y: secondaryCenter.y - secondaryRadius * 0.6,
            width: secondaryRadius * 2,
            height: secondaryRadius * 1.2
        ))

        highlightContext.fill(
            secondaryPath,
            with: .radialGradient(
                Gradient(colors: [
                    Color.white.opacity(highlightOpacity * 0.7),
                    Color.clear,
                ]),
                center: secondaryCenter,
                startRadius: 0,
                endRadius: secondaryRadius
            )
        )
    }

    // MARK: - Fresnel Rim

    private func drawFresnelRim(
        context: GraphicsContext,
        center: CGPoint,
        radius: CGFloat,
        time: Double
    ) {
        // Bright edge ring — simulates Fresnel reflection
        let rimShift = sin(time * 0.5) * 0.03
        let rimPath = Path(ellipseIn: CGRect(
            x: center.x - radius,
            y: center.y - radius,
            width: radius * 2,
            height: radius * 2
        ))

        let rimOpacity = 0.25 + rimShift
        let audioPulse = state == .listening ? (1.0 + audioLevel * 0.4) : 1.0

        // Stroke-based rim
        var rimContext = context
        rimContext.stroke(
            rimPath,
            with: .linearGradient(
                Gradient(colors: [
                    Self.highlightGold.opacity(rimOpacity * audioPulse),
                    Self.primaryAmber.opacity(rimOpacity * 0.5 * audioPulse),
                    Self.highlightGold.opacity(rimOpacity * 0.8 * audioPulse),
                    Self.primaryAmber.opacity(rimOpacity * 0.3 * audioPulse),
                ]),
                startPoint: CGPoint(x: center.x - radius, y: center.y - radius),
                endPoint: CGPoint(x: center.x + radius, y: center.y + radius)
            ),
            lineWidth: radius * 0.06
        )

        // Inner soft glow band (wider, fainter)
        let innerRimInset = radius * 0.04
        let innerRimPath = Path(ellipseIn: CGRect(
            x: center.x - radius + innerRimInset,
            y: center.y - radius + innerRimInset,
            width: (radius - innerRimInset) * 2,
            height: (radius - innerRimInset) * 2
        ))

        rimContext.stroke(
            innerRimPath,
            with: .linearGradient(
                Gradient(colors: [
                    Self.primaryAmber.opacity(0.10 * audioPulse),
                    Self.highlightGold.opacity(0.15 * audioPulse),
                    Self.primaryAmber.opacity(0.08 * audioPulse),
                ]),
                startPoint: CGPoint(x: center.x, y: center.y - radius),
                endPoint: CGPoint(x: center.x, y: center.y + radius)
            ),
            lineWidth: radius * 0.10
        )
    }

    // MARK: - Warped Circle Path

    /// Creates a slightly organic circle with sinusoidal displacement.
    private func warpedCirclePath(
        center: CGPoint,
        radius: CGFloat,
        time: Double,
        amplitude: CGFloat
    ) -> Path {
        let segments = 64
        var path = Path()

        for i in 0...segments {
            let angle = Double(i) / Double(segments) * .pi * 2

            // Multiple frequency warp for organic feel
            let warp1 = sin(angle * 3 + time * 0.6) * amplitude
            let warp2 = sin(angle * 5 + time * 0.4) * amplitude * 0.5
            let warp3 = cos(angle * 7 + time * 0.8) * amplitude * 0.3

            let thinkingWarp = state == .thinking ? sin(time * 3.0) * amplitude * 0.5 : 0
            let listeningWarp = state == .listening ? audioLevel * amplitude * 2.0 * sin(angle * 2 + time * 2.0) : 0

            let r = radius + warp1 + warp2 + warp3 + thinkingWarp + listeningWarp

            let point = CGPoint(
                x: center.x + cos(angle) * r,
                y: center.y + sin(angle) * r
            )

            if i == 0 {
                path.move(to: point)
            } else {
                path.addLine(to: point)
            }
        }

        path.closeSubpath()
        return path
    }

    // MARK: - Animation Speed

    private var animationSpeed: Double {
        switch state {
        case .idle:
            return 0.5
        case .thinking:
            return 1.5
        case .success:
            return 0.8
        case .listening:
            return 0.7 + Double(audioLevel) * 1.0
        }
    }
}

// MARK: - Preview

#if DEBUG
struct HestiaOrbView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 40) {
                HestiaOrbView(state: .idle, size: 120)
                HestiaOrbView(state: .thinking, size: 120)
                HestiaOrbView(state: .listening, size: 120, audioLevel: 0.6)
            }
        }
        .previewDisplayName("Orb States")
    }
}
#endif
