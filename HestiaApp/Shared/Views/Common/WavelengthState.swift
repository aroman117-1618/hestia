// WavelengthState.swift
// HestiaApp
//
// Particle wave state, parameters, and particle model.
// Ported from ParticleWave.tsx (Figma Make reference).

import Foundation
import CoreGraphics

// MARK: - Wavelength Mode

enum WavelengthMode: Equatable {
    case idle
    case listening
    case speaking
    case thinking
}

// MARK: - Color Palette

/// Amber/gold palette matching ParticleWave.tsx COLORS array.
enum WavelengthPalette {
    static let colors: [(r: CGFloat, g: CGFloat, b: CGFloat)] = [
        (255/255, 240/255, 208/255), // #FFF0D0 — Brightest highlights
        (255/255, 179/255,  71/255), // #FFB347 — Bright amber
        (255/255, 159/255,  10/255), // #FF9F0A — Primary amber
        (224/255, 138/255,   0/255), // #E08A00 — Mid amber
        (192/255, 104/255,   0/255), // #C06800 — Deep orange
        (139/255,  69/255,   0/255), // #8B4500 — Ember
        (255/255, 215/255,   0/255), // #FFD700 — Gold shimmer
    ]

    static var count: Int { colors.count }
}

// MARK: - Animation Parameters

struct WavelengthParams {
    var speedMult: Double
    var ampMult: Double
    var glowMult: Double
    var densityMult: Double
    var audioVol: Double

    static func target(for mode: WavelengthMode) -> WavelengthParams {
        switch mode {
        case .idle, .listening:
            return WavelengthParams(
                speedMult: 1.0,
                ampMult: 1.5,
                glowMult: 0.7,
                densityMult: 1.0,
                audioVol: 0.0
            )
        case .speaking, .thinking:
            return WavelengthParams(
                speedMult: 1.5,
                ampMult: 2.0,
                glowMult: 0.7,
                densityMult: 1.5,
                audioVol: 1.0
            )
        }
    }

    func lerped(toward target: WavelengthParams, alpha: Double) -> WavelengthParams {
        let a = min(max(alpha, 0), 1)
        return WavelengthParams(
            speedMult:   speedMult   + (target.speedMult   - speedMult)   * a,
            ampMult:     ampMult     + (target.ampMult     - ampMult)     * a,
            glowMult:    target.glowMult, // Locked — no interpolation (matches TSX)
            densityMult: densityMult + (target.densityMult - densityMult) * a,
            audioVol:    audioVol    + (target.audioVol    - audioVol)    * a
        )
    }
}

// MARK: - Particle

struct Particle {
    var x: Double
    var yOffset: Double
    let z: Double          // depth 0.4–1.0
    let ribbon: Int        // 0, 1, or 2
    let speedX: Double
    let colorIdx: Int
    let isHero: Bool
    let baseSize: Double
    let isScattered: Bool
    let phaseOffset: Double

    static func create(width: Double, height: Double) -> Particle {
        let z = Double.random(in: 0.4...1.0)
        let ribbon = Int.random(in: 0...2)
        let speedX = Double.random(in: 0.2...0.6) * z
        let colorIdx = Int.random(in: 0..<WavelengthPalette.count)
        let isHero = Double.random(in: 0...1) < 0.03
        let baseSize = isHero
            ? Double.random(in: 4...7)
            : Double.random(in: 1.5...3.5)
        let isScattered = Double.random(in: 0...1) < 0.15
        let yOffset = isScattered
            ? (Double.random(in: 0...1) - 0.5) * 180
            : (Double.random(in: 0...1) - 0.5) * 40
        let phaseOffset = Double.random(in: 0...(Double.pi * 2))
        let x = Double.random(in: 0..<width)

        return Particle(
            x: x,
            yOffset: yOffset,
            z: z,
            ribbon: ribbon,
            speedX: speedX,
            colorIdx: colorIdx,
            isHero: isHero,
            baseSize: baseSize,
            isScattered: isScattered,
            phaseOffset: phaseOffset
        )
    }
}
