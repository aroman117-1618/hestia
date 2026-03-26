// WavelengthRenderer.swift
// HestiaApp
//
// Particle wave renderer — produces a CGImage per frame.
// Ported from ParticleWave.tsx (Figma Make reference).
// iOS-only (UIGraphicsImageRenderer). macOS stub returns nil.

import CoreGraphics
import Foundation

#if os(iOS)
import UIKit
#endif

// MARK: - Wavelength Renderer

struct WavelengthRenderer {

    // MARK: - Texture Cache

    /// Pre-rendered radial gradient textures per color (normal + hero).
    struct TextureSet {
        let normal: CGImage  // 32x32
        let hero: CGImage    // 64x64
    }

    #if os(iOS)
    /// Create cached particle textures for all palette colors.
    static func createTextures() -> [TextureSet] {
        WavelengthPalette.colors.map { color in
            TextureSet(
                normal: createParticleTexture(r: color.r, g: color.g, b: color.b, size: 32, isHero: false),
                hero: createParticleTexture(r: color.r, g: color.g, b: color.b, size: 64, isHero: true)
            )
        }
    }

    private static func createParticleTexture(
        r: CGFloat, g: CGFloat, b: CGFloat,
        size: Int, isHero: Bool
    ) -> CGImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1.0
        format.opaque = false

        let cgSize = CGSize(width: size, height: size)
        let renderer = UIGraphicsImageRenderer(size: cgSize, format: format)

        let image = renderer.image { rendererCtx in
            let ctx = rendererCtx.cgContext
            let center = CGFloat(size) / 2
            let colorSpace = CGColorSpaceCreateDeviceRGB()

            // Radial gradient: opaque center -> transparent edge
            // Matches TSX stops: 0, 0.15/0.08, 0.35/0.22, 1.0
            let stop1 = isHero ? 0.15 : 0.08
            let stop2 = isHero ? 0.35 : 0.22

            let components: [CGFloat] = [
                r, g, b, 1.0,
                r, g, b, 0.8,
                r, g, b, 0.2,
                r, g, b, 0.0,
            ]
            let locations: [CGFloat] = [0.0, CGFloat(stop1), CGFloat(stop2), 1.0]

            if let gradient = CGGradient(
                colorSpace: colorSpace,
                colorComponents: components,
                locations: locations,
                count: 4
            ) {
                ctx.drawRadialGradient(
                    gradient,
                    startCenter: CGPoint(x: center, y: center),
                    startRadius: 0,
                    endCenter: CGPoint(x: center, y: center),
                    endRadius: center,
                    options: []
                )
            }
        }

        // Force unwrap is safe — UIGraphicsImageRenderer always produces a valid image
        return image.cgImage!
    }
    #endif

    // MARK: - Frame Rendering

    #if os(iOS)
    /// Render one complete particle wave frame to a CGImage.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        speakingTime: Double,
        params: WavelengthParams,
        particles: inout [Particle],
        textures: [TextureSet],
        waveScale: CGFloat
    ) -> CGImage? {
        let width = size.width
        let height = size.height
        let centerY = height / 2

        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = true

        let renderer = UIGraphicsImageRenderer(size: size, format: format)

        let image = renderer.image { rendererCtx in
            let ctx = rendererCtx.cgContext

            // Clear to #020101
            ctx.setFillColor(CGColor(red: 2/255, green: 1/255, blue: 1/255, alpha: 1))
            ctx.fill(CGRect(origin: .zero, size: size))

            // Additive blending
            ctx.setBlendMode(.plusLighter)

            let maxParticles = 3500
            let visibleCount = min(
                Int(Double(maxParticles) * 0.66 * params.densityMult),
                particles.count
            )

            let active = params.audioVol
            let currentGlow = params.glowMult
            let wScale = Double(waveScale)

            for i in 0..<visibleCount {
                // Move particle
                particles[i].x += particles[i].speedX * params.speedMult
                if particles[i].x > Double(width) {
                    particles[i].x = 0
                    particles[i].yOffset = particles[i].isScattered
                        ? (Double.random(in: 0...1) - 0.5) * 180
                        : (Double.random(in: 0...1) - 0.5) * 40
                }

                let p = particles[i]
                let normalizedX = p.x / Double(width)

                // === TAPER ===
                let distFromCenter = abs(normalizedX - 0.5) * 2.2
                let taper = max(0, 1 - distFromCenter * distFromCenter)

                // Early out
                let alpha = taper * p.z
                if alpha <= 0.01 { continue }

                // === CALM LISTENING WAVE ===
                var calmY: Double = 0
                switch p.ribbon {
                case 0:
                    calmY = sin(normalizedX * .pi * 3 + time * 2) * 45
                        + sin(normalizedX * .pi * 2 - time) * 20
                case 1:
                    calmY = sin(normalizedX * .pi * 4 + time * 1.5 + p.phaseOffset) * 35
                default:
                    calmY = sin(normalizedX * .pi * 2.5 + time * 2.5 + p.phaseOffset) * 40
                }
                calmY *= params.ampMult

                // === SPEAKING WAVE (asymmetric) ===
                let t = speakingTime
                var angle1: Double = 0
                var angle2: Double = 0
                var rawWave: Double = 0
                var baseAmp: Double = 0
                var asymmetry: Double = 0
                var troughDampening: Double = 0

                switch p.ribbon {
                case 0:
                    angle1 = normalizedX * .pi * 2.5 - t * 1.2
                    angle2 = normalizedX * .pi * 1.5 + t * 0.8
                    rawWave = (sin(angle1) + sin(angle2) * 0.5) / 1.5
                    baseAmp = 35
                    asymmetry = 1.3
                    troughDampening = 0.5
                case 1:
                    angle1 = normalizedX * .pi * 4.0 - t * 1.8
                    angle2 = normalizedX * .pi * 2.0 - t * 1.5
                    rawWave = (sin(angle1) + cos(angle2) * 0.6) / 1.6
                    baseAmp = 40
                    asymmetry = 1.7
                    troughDampening = 0.3
                default:
                    angle1 = normalizedX * .pi * 3.0 + t * 2.4
                    angle2 = normalizedX * .pi * 4.5 - t * 2.0
                    rawWave = (sin(angle1) + sin(angle2) * 0.4) / 1.4
                    baseAmp = 45
                    asymmetry = 2.2
                    troughDampening = 0.15
                }

                var speakingY: Double = 0
                if rawWave > 0 {
                    speakingY = -pow(rawWave, 1.5) * baseAmp * params.ampMult * asymmetry
                } else {
                    speakingY = abs(rawWave) * baseAmp * params.ampMult * troughDampening
                }

                let speakingThicknessMap = rawWave > 0
                    ? (1.0 + pow(rawWave, 2) * 1.5)
                    : (1.0 - abs(rawWave) * 0.6)

                // === BLEND ===
                var waveY = calmY * (1.0 - active) + speakingY * active
                let finalThickness = 1.0 * (1.0 - active) + speakingThicknessMap * active
                let swirl = sin(p.phaseOffset + t * 2.5) * (15 * active)

                let currentYOffset = (p.yOffset + swirl) * finalThickness

                waveY *= taper

                // Apply waveScale to vertical components
                let y = Double(centerY) + (waveY * wScale) + (currentYOffset * p.z * taper * wScale)

                // === DRAW ===
                let particleSize = p.baseSize * p.z
                let drawSize = particleSize * 6

                let tex = textures[p.colorIdx]
                let texImage = p.isHero ? tex.hero : tex.normal

                ctx.setAlpha(CGFloat(alpha * currentGlow))
                ctx.draw(
                    texImage,
                    in: CGRect(
                        x: p.x - drawSize / 2,
                        y: y - drawSize / 2,
                        width: drawSize,
                        height: drawSize
                    )
                )
            }
        }

        return image.cgImage
    }
    #else
    /// macOS stub — particle wave renderer is iOS-only.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        speakingTime: Double,
        params: WavelengthParams,
        particles: inout [Particle],
        textures: Any,
        waveScale: CGFloat
    ) -> CGImage? {
        return nil
    }

    static func createTextures() -> [Any] { [] }
    #endif
}
