// WavelengthRenderer.swift
// HestiaApp
//
// Particle wave renderer — produces a CGImage per frame.
// Ported from ParticleWave.tsx (Figma Make reference).
// iOS-only (UIGraphicsImageRenderer). macOS stub returns nil.
//
// Performance: pre-computed wave tables eliminate per-particle trig.
// 2000 particles with larger sizes = same density, ~50% less work.

import CoreGraphics
import Foundation

#if os(iOS)
import UIKit
#endif

// MARK: - Wave Table (pre-computed per frame)

/// Pre-computed wave Y values for 128 X-buckets across 3 ribbons.
/// Eliminates ~4000 sin() calls per frame.
struct WaveTable {
    static let bucketCount = 128

    /// Calm wave Y values: [bucket * 3 + ribbon]
    var calm = [Double](repeating: 0, count: bucketCount * 3)
    /// Speaking raw wave values: [bucket * 3 + ribbon]
    var speak = [Double](repeating: 0, count: bucketCount * 3)

    mutating func compute(time: Double, speakingTime: Double) {
        let t = speakingTime
        for bucket in 0..<Self.bucketCount {
            let nx = Double(bucket) / Double(Self.bucketCount)

            // Calm waves (3 ribbons)
            calm[bucket * 3 + 0] = sin(nx * .pi * 3 + time * 2) * 45
                + sin(nx * .pi * 2 - time) * 20
            calm[bucket * 3 + 1] = sin(nx * .pi * 4 + time * 1.5) * 35
            calm[bucket * 3 + 2] = sin(nx * .pi * 2.5 + time * 2.5) * 40

            // Speaking waves (3 ribbons)
            let a0 = nx * .pi * 2.5 - t * 1.2
            let b0 = nx * .pi * 1.5 + t * 0.8
            speak[bucket * 3 + 0] = (sin(a0) + sin(b0) * 0.5) / 1.5

            let a1 = nx * .pi * 4.0 - t * 1.8
            let b1 = nx * .pi * 2.0 - t * 1.5
            speak[bucket * 3 + 1] = (sin(a1) + cos(b1) * 0.6) / 1.6

            let a2 = nx * .pi * 3.0 + t * 2.4
            let b2 = nx * .pi * 4.5 - t * 2.0
            speak[bucket * 3 + 2] = (sin(a2) + sin(b2) * 0.4) / 1.4
        }
    }
}

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

        return image.cgImage!
    }
    #endif

    // MARK: - Frame Rendering

    #if os(iOS)
    /// Render one complete particle wave frame to a CGImage.
    /// Uses pre-computed wave tables for performance.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        speakingTime: Double,
        params: WavelengthParams,
        particles: inout [Particle],
        textures: [TextureSet],
        waveScale: CGFloat,
        waveTable: WaveTable
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

            let maxParticles = 2000  // down from 3500 — bigger particles compensate
            let visibleCount = min(
                Int(Double(maxParticles) * 0.66 * params.densityMult),
                particles.count
            )

            let active = params.audioVol
            let currentGlow = params.glowMult
            let wScale = Double(waveScale)

            // Pre-extracted constants for speaking wave
            let baseAmps: [Double] = [35, 40, 45]
            let asymmetries: [Double] = [1.3, 1.7, 2.2]
            let troughDamps: [Double] = [0.5, 0.3, 0.15]
            let bucketCount = Double(WaveTable.bucketCount)

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

                // Early out — raised from 0.01 to 0.05 (skips ~200 barely-visible particles)
                let alpha = taper * p.z
                if alpha <= 0.05 { continue }

                // === WAVE TABLE LOOKUP (replaces per-particle sin() calls) ===
                let bucket = min(Int(normalizedX * bucketCount), WaveTable.bucketCount - 1)
                let ribbon = p.ribbon
                let tableIdx = bucket * 3 + ribbon

                // Calm wave from table + per-particle phase variation
                var calmY = waveTable.calm[tableIdx]
                calmY += sin(p.phaseOffset + time) * 8  // cheap per-particle variation
                calmY *= params.ampMult

                // Speaking wave from table
                let rawWave = waveTable.speak[tableIdx]
                var speakingY: Double = 0
                if rawWave > 0 {
                    speakingY = -pow(rawWave, 1.5) * baseAmps[ribbon] * params.ampMult * asymmetries[ribbon]
                } else {
                    speakingY = abs(rawWave) * baseAmps[ribbon] * params.ampMult * troughDamps[ribbon]
                }

                let speakingThicknessMap = rawWave > 0
                    ? (1.0 + rawWave * rawWave * 1.5)
                    : (1.0 - abs(rawWave) * 0.6)

                // === BLEND ===
                var waveY = calmY * (1.0 - active) + speakingY * active
                let finalThickness = 1.0 * (1.0 - active) + speakingThicknessMap * active
                let swirl = sin(p.phaseOffset + speakingTime * 2.5) * (15 * active)

                let currentYOffset = (p.yOffset + swirl) * finalThickness

                waveY *= taper

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
    /// Create cached particle textures for all palette colors (macOS — pure CoreGraphics).
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
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let ctx = CGContext(
            data: nil,
            width: size, height: size,
            bitsPerComponent: 8, bytesPerRow: size * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!

        let center = CGFloat(size) / 2
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

        return ctx.makeImage()!
    }

    /// Render one complete particle wave frame to a CGImage (macOS — pure CoreGraphics).
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        speakingTime: Double,
        params: WavelengthParams,
        particles: inout [Particle],
        textures: [TextureSet],
        waveScale: CGFloat,
        waveTable: WaveTable
    ) -> CGImage? {
        let width = size.width
        let height = size.height
        let centerY = height / 2

        let pixelWidth = Int(width * scale)
        let pixelHeight = Int(height * scale)
        guard pixelWidth > 0, pixelHeight > 0 else { return nil }

        let colorSpace = CGColorSpaceCreateDeviceRGB()
        guard let ctx = CGContext(
            data: nil,
            width: pixelWidth, height: pixelHeight,
            bitsPerComponent: 8, bytesPerRow: pixelWidth * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }

        // Scale context to match logical size
        ctx.scaleBy(x: scale, y: scale)

        // Clear to #020101
        ctx.setFillColor(CGColor(red: 2/255, green: 1/255, blue: 1/255, alpha: 1))
        ctx.fill(CGRect(origin: .zero, size: size))

        // Additive blending
        ctx.setBlendMode(.plusLighter)

        let maxParticles = 2000
        let visibleCount = min(
            Int(Double(maxParticles) * 0.66 * params.densityMult),
            particles.count
        )

        let active = params.audioVol
        let currentGlow = params.glowMult
        let wScale = Double(waveScale)

        let baseAmps: [Double] = [35, 40, 45]
        let asymmetries: [Double] = [1.3, 1.7, 2.2]
        let troughDamps: [Double] = [0.5, 0.3, 0.15]
        let bucketCount = Double(WaveTable.bucketCount)

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

            let alpha = taper * p.z
            if alpha <= 0.05 { continue }

            // === WAVE TABLE LOOKUP ===
            let bucket = min(Int(normalizedX * bucketCount), WaveTable.bucketCount - 1)
            let ribbon = p.ribbon
            let tableIdx = bucket * 3 + ribbon

            var calmY = waveTable.calm[tableIdx]
            calmY += sin(p.phaseOffset + time) * 8
            calmY *= params.ampMult

            let rawWave = waveTable.speak[tableIdx]
            var speakingY: Double = 0
            if rawWave > 0 {
                speakingY = -pow(rawWave, 1.5) * baseAmps[ribbon] * params.ampMult * asymmetries[ribbon]
            } else {
                speakingY = abs(rawWave) * baseAmps[ribbon] * params.ampMult * troughDamps[ribbon]
            }

            let speakingThicknessMap = rawWave > 0
                ? (1.0 + rawWave * rawWave * 1.5)
                : (1.0 - abs(rawWave) * 0.6)

            // === BLEND ===
            var waveY = calmY * (1.0 - active) + speakingY * active
            let finalThickness = 1.0 * (1.0 - active) + speakingThicknessMap * active
            let swirl = sin(p.phaseOffset + speakingTime * 2.5) * (15 * active)

            let currentYOffset = (p.yOffset + swirl) * finalThickness

            waveY *= taper

            // CGContext has flipped Y (origin at bottom-left), so flip the Y coordinate
            let logicalY = Double(centerY) + (waveY * wScale) + (currentYOffset * p.z * taper * wScale)
            let y = Double(height) - logicalY

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

        return ctx.makeImage()
    }
    #endif
}
