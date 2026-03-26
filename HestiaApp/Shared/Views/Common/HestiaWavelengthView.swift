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
    private var initializing = false

    private func ensureInitialized(width: Double, height: Double) {
        guard !initialized, !initializing else { return }
        initializing = true

        // Allocate particles + textures off main thread to prevent watchdog kill
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let count = 3500
            var newParticles: [Particle] = []
            newParticles.reserveCapacity(count)
            for _ in 0..<count {
                newParticles.append(Particle.create(width: width, height: height))
            }

            #if os(iOS)
            let newTextures = WavelengthRenderer.createTextures()
            #endif

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.particles = newParticles
                #if os(iOS)
                self.textures = newTextures
                #endif
                self.initialized = true
                #if os(iOS)
                NSLog("[Wavelength] Initialized: %d particles, %d textures", newParticles.count, self.textures.count)
                #else
                NSLog("[Wavelength] Initialized: %d particles", newParticles.count)
                #endif
            }
        }
    }

    private var isRendering = false

    func update(
        date: Date,
        mode: WavelengthMode,
        audioLevel: CGFloat,
        size: CGSize,
        waveScale: CGFloat
    ) {
        ensureInitialized(width: Double(size.width), height: Double(size.height))
        guard initialized, !particles.isEmpty else { return }
        // Skip if previous frame is still rendering
        guard !isRendering else { return }

        let now = date.timeIntervalSinceReferenceDate
        let dt = lastTimestamp == 0 ? 0.016 : min(0.033, now - lastTimestamp)
        lastTimestamp = now

        let target = WavelengthParams.target(for: mode)
        if let current = currentParams {
            currentParams = current.lerped(toward: target, alpha: 0.05)
        } else {
            currentParams = target
        }

        guard let p = currentParams else { return }

        globalTime += 0.005 * p.speedMult
        speakingTime += dt * (1 + p.audioVol * 4)

        #if os(iOS)
        // Render off main thread to prevent CPU saturation
        isRendering = true
        let renderTime = globalTime
        let renderSpeakingTime = speakingTime
        let renderParams = p
        let renderSize = size
        let renderScale: CGFloat = 1.0  // Render at 1x, display scales up (saves 4x CPU vs 3x retina)
        let renderWaveScale = waveScale
        var renderParticles = particles  // Value copy for thread safety

        DispatchQueue.global(qos: .userInteractive).async { [weak self] in
            guard let self else { return }

            let frame = WavelengthRenderer.renderToImage(
                size: renderSize,
                scale: renderScale,
                time: renderTime,
                speakingTime: renderSpeakingTime,
                params: renderParams,
                particles: &renderParticles,
                textures: self.textures,
                waveScale: renderWaveScale
            )

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.particles = renderParticles  // Sync particle positions back
                self.renderedFrame = frame
                self.isRendering = false
            }
        }
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
        case .idle:
            return 1.0 / 15.0    // 15fps idle — saves battery
        case .listening:
            return 1.0 / 20.0
        case .speaking, .thinking:
            return 1.0 / 24.0    // 24fps is smooth enough, saves CPU vs 30
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
                    // Rendered at 1x for performance, .resizable() scales to fill frame
                    Image(cgImage, scale: 1.0, label: Text("Hestia wavelength"))
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
