// WavelengthState.swift
// HestiaApp
//
// Wavelength animation state, band definitions, and parameter interpolation.

import Foundation

// MARK: - Wavelength State

enum WavelengthMode: Equatable {
    case idle
    case listening
    case speaking
    case thinking
}

// MARK: - Band Definition

struct WavelengthBand {
    let tx: Double
    let ty: Double
    let off: Double
    let w: Double
    let b: Double
    let wv: (Double, Double, Double)

    static let bands: [WavelengthBand] = [
        WavelengthBand(tx:  0.52, ty:  0.28, off: 0.00, w: 1.00, b: 1.00, wv: (3.0, 5.2, 7.8)),
        WavelengthBand(tx: -0.38, ty:  0.84, off: 2.09, w: 0.76, b: 0.82, wv: (2.4, 4.7, 8.3)),
        WavelengthBand(tx:  0.72, ty: -0.52, off: 4.19, w: 0.48, b: 0.62, wv: (3.6, 6.1, 9.0)),
    ]
}

// MARK: - 3D Point

struct WavelengthPoint {
    let x: Double
    let y: Double
    let z: Double
    let depth: Double
}

// MARK: - Animation Parameters

struct WavelengthParams {
    var spd: Double
    var bloom: Double
    var pulse: Double
    var bw: Double
    var glow: Double
    var bg: Double
    var rim: Double
    var sph: Double
    var wave: Double
    var wSpd: Double

    static func target(for mode: WavelengthMode, level: Double, time: Double) -> WavelengthParams {
        switch mode {
        case .idle:
            return WavelengthParams(
                spd: 0.30,
                bloom: 0.80 + level * 0.10,
                pulse: 0.003 + 0.003 * sin(time * 0.7),
                bw: 0.90 + level * 0.05,
                glow: 0.85 + level * 0.08,
                bg: 0.30 + level * 0.08,
                rim: 0.40 + level * 0.08,
                sph: 0.85,
                wave: 0.045,
                wSpd: 0.8
            )
        case .listening:
            return WavelengthParams(
                spd: 0.45,
                bloom: 0.92 + level * 0.18,
                pulse: 0.005 + 0.004 * sin(time * 0.9),
                bw: 1.00 + level * 0.08,
                glow: 1.00 + level * 0.12,
                bg: 0.38 + level * 0.10,
                rim: 0.50 + level * 0.10,
                sph: 0.82,
                wave: 0.055,
                wSpd: 1.0
            )
        case .thinking:
            return WavelengthParams(
                spd: 0.65,
                bloom: 1.20 + 0.15 * sin(time * 2.0),
                pulse: 0.010 + 0.008 * sin(time * 1.8),
                bw: 1.15 + 0.05 * sin(time * 2.2),
                glow: 1.25 + 0.12 * sin(time * 2.5),
                bg: 0.50 + 0.10 * sin(time * 1.5),
                rim: 0.65 + 0.08 * sin(time * 2.0),
                sph: 0.72,
                wave: 0.065,
                wSpd: 1.4
            )
        case .speaking:
            return WavelengthParams(
                spd: 0.90 + level * 0.25,
                bloom: 1.55 + level * 0.50 + 0.28 * sin(time * 3.2),
                pulse: 0.016 + 0.012 * sin(time * 2.5),
                bw: 1.30 + level * 0.18 + 0.06 * sin(time * 2.8),
                glow: 1.50 + level * 0.35 + 0.18 * sin(time * 3.5),
                bg: 0.62 + level * 0.28 + 0.12 * sin(time * 2.2),
                rim: 0.80 + level * 0.20 + 0.08 * sin(time * 3.0),
                sph: 0.62 - level * 0.10,
                wave: 0.08 + level * 0.03,
                wSpd: 1.8 + level * 0.6
            )
        }
    }

    func lerped(toward target: WavelengthParams, alpha: Double) -> WavelengthParams {
        let a = min(max(alpha, 0), 1)
        return WavelengthParams(
            spd:   spd   + (target.spd   - spd)   * a,
            bloom: bloom + (target.bloom - bloom) * a,
            pulse: pulse + (target.pulse - pulse) * a,
            bw:    bw    + (target.bw    - bw)    * a,
            glow:  glow  + (target.glow  - glow)  * a,
            bg:    bg    + (target.bg    - bg)    * a,
            rim:   rim   + (target.rim   - rim)   * a,
            sph:   sph   + (target.sph   - sph)   * a,
            wave:  wave  + (target.wave  - wave)  * a,
            wSpd:  wSpd  + (target.wSpd  - wSpd)  * a
        )
    }
}
