// HestiaWavelengthView.swift
// HestiaApp
//
// SwiftUI wrapper for the particle wave renderer.
// Owns particles, textures, timing, and frame output.

import SwiftUI

// MARK: - ViewModel

@MainActor
final class WavelengthViewModel: ObservableObject {
    @Published var renderedFrame: CGImage?

    private var particles: [Particle] = []
    private var currentParams: WavelengthParams?
    private var globalTime: Double = 0
    private var speakingTime: Double = 0
    private var lastTimestamp: TimeInterval = 0

    #if os(iOS)
    private var textures: [WavelengthRenderer.TextureSet] = []
    #endif

    private var initialized = false

    private func ensureInitialized(width: Double, height: Double) {
        guard !initialized else { return }
        initialized = true

        let count = 3500
        particles.reserveCapacity(count)
        for _ in 0..<count {
            particles.append(Particle.create(width: width, height: height))
        }

        #if os(iOS)
        textures = WavelengthRenderer.createTextures()
        #endif
    }

    func update(
        date: Date,
        mode: WavelengthMode,
        audioLevel: CGFloat,
        size: CGSize,
        waveScale: CGFloat
    ) {
        ensureInitialized(width: Double(size.width), height: Double(size.height))

        let now = date.timeIntervalSinceReferenceDate
        let dt = lastTimestamp == 0 ? 0.016 : min(0.033, now - lastTimestamp)
        lastTimestamp = now

        // Target params
        let target = WavelengthParams.target(for: mode)

        // Lerp at 0.05 per frame (matches TSX)
        if let current = currentParams {
            currentParams = current.lerped(toward: target, alpha: 0.05)
        } else {
            currentParams = target
        }

        guard let p = currentParams else { return }

        // Update time accumulators
        globalTime += 0.005 * p.speedMult
        // Speaking time runs faster: dt * (1 + audioVol * 4)
        speakingTime += dt * (1 + p.audioVol * 4)

        #if os(iOS)
        let displayScale = UITraitCollection.current.displayScale

        renderedFrame = WavelengthRenderer.renderToImage(
            size: size,
            scale: displayScale,
            time: globalTime,
            speakingTime: speakingTime,
            params: p,
            particles: &particles,
            textures: textures,
            waveScale: waveScale
        )
        #endif
    }
}

// MARK: - View

struct HestiaWavelengthView: View {
    let mode: WavelengthMode
    var audioLevel: CGFloat = 0.0
    var waveScale: CGFloat = 1.0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @StateObject private var viewModel = WavelengthViewModel()

    private var frameInterval: Double {
        switch mode {
        case .idle, .listening:
            return 1.0 / 20.0
        case .speaking, .thinking:
            return 1.0 / 30.0
        }
    }

    var body: some View {
        if reduceMotion {
            staticFallback
        } else {
            animatedWavelength
        }
    }

    // MARK: - Animated View

    private var animatedWavelength: some View {
        GeometryReader { geo in
            TimelineView(.animation(minimumInterval: frameInterval)) { timeline in
                let _ = viewModel.update(
                    date: timeline.date,
                    mode: mode,
                    audioLevel: audioLevel,
                    size: geo.size,
                    waveScale: waveScale
                )

                if let cgImage = viewModel.renderedFrame {
                    #if os(iOS)
                    let displayScale = UITraitCollection.current.displayScale
                    #else
                    let displayScale: CGFloat = NSScreen.main?.backingScaleFactor ?? 2.0
                    #endif

                    Image(cgImage, scale: displayScale, label: Text("Hestia wavelength"))
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: geo.size.width, height: geo.size.height)
                } else {
                    Color(red: 2/255, green: 1/255, blue: 1/255)
                        .frame(width: geo.size.width, height: geo.size.height)
                }
            }
        }
    }

    // MARK: - Static Fallback (Reduce Motion)

    private var staticFallback: some View {
        Rectangle()
            .fill(Color(red: 2/255, green: 1/255, blue: 1/255))
            .overlay(
                LinearGradient(
                    colors: [
                        Color(red: 1, green: 159.0/255.0, blue: 10.0/255.0).opacity(0.15),
                        .clear,
                        Color(red: 1, green: 159.0/255.0, blue: 10.0/255.0).opacity(0.15)
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
    }
}

#if DEBUG
#Preview("Wavelength - Idle") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .idle)
            .frame(height: 200)
    }
}

#Preview("Wavelength - Speaking") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .speaking, audioLevel: 0.6)
            .frame(height: 200)
    }
}

#Preview("Wavelength - Scaled Down") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .listening, waveScale: 0.5)
            .frame(height: 200)
    }
}
#endif
