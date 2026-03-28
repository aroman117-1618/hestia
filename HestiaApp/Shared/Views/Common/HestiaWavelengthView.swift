// HestiaWavelengthView.swift
// HestiaApp
//
// SwiftUI wrapper for the wavelength particle animation.
// Uses Metal on device (60fps GPU-accelerated) with CGContext fallback for simulator.

import SwiftUI

// MARK: - View

struct HestiaWavelengthView: View {
    let mode: WavelengthMode
    var audioLevel: CGFloat = 0.0
    var waveScale: CGFloat = 1.0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if reduceMotion {
            staticFallback
        } else {
            metalWavelength
        }
    }

    // MARK: - Metal View (Device)

    private var metalWavelength: some View {
        #if os(iOS) && !targetEnvironment(simulator)
        MetalParticleView(mode: mode, audioLevel: audioLevel, waveScale: waveScale)
        #else
        cgContextFallback
        #endif
    }

    // MARK: - CGContext Fallback (Simulator / macOS)

    @StateObject private var fallbackVM = WavelengthFallbackViewModel()

    private var cgContextFallback: some View {
        GeometryReader { geo in
            #if os(macOS)
            let interval = 1.0 / 30.0
            #else
            let interval = 1.0 / 15.0
            #endif
            TimelineView(.animation(minimumInterval: interval)) { timeline in
                let _ = fallbackVM.update(
                    date: timeline.date,
                    mode: mode,
                    audioLevel: audioLevel,
                    size: geo.size,
                    waveScale: waveScale
                )

                if let cgImage = fallbackVM.renderedFrame {
                    Image(cgImage, scale: 2.0, label: Text("Hestia wavelength"))
                        .interpolation(.high)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: geo.size.width, height: geo.size.height)
                } else {
                    Color.clear
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

// MARK: - Fallback ViewModel (Simulator / macOS)

@MainActor
final class WavelengthFallbackViewModel: ObservableObject {
    @Published var renderedFrame: CGImage?

    private var particles: [Particle] = []
    private var currentParams: WavelengthParams?
    private var globalTime: Double = 0
    private var speakingTime: Double = 0
    private var lastTimestamp: TimeInterval = 0
    private var waveTable = WaveTable()
    private var textures: [WavelengthRenderer.TextureSet] = []
    private var initialized = false
    private var initializing = false
    private var isRendering = false

    private func ensureInitialized(width: Double, height: Double) {
        guard !initialized, !initializing else { return }
        initializing = true

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let count = 2000
            var newParticles: [Particle] = []
            newParticles.reserveCapacity(count)
            for _ in 0..<count {
                newParticles.append(Particle.create(width: width, height: height))
            }
            let newTextures = WavelengthRenderer.createTextures()

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.particles = newParticles
                self.textures = newTextures
                self.initialized = true
            }
        }
    }

    func update(
        date: Date,
        mode: WavelengthMode,
        audioLevel: CGFloat,
        size: CGSize,
        waveScale: CGFloat
    ) {
        ensureInitialized(width: Double(size.width), height: Double(size.height))
        guard initialized, !particles.isEmpty, !isRendering else { return }

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
        waveTable.compute(time: globalTime, speakingTime: speakingTime)

        isRendering = true
        let renderTime = globalTime
        let renderSpeakingTime = speakingTime
        let renderParams = p
        let renderSize = size
        let renderWaveScale = waveScale
        var renderParticles = particles
        let renderWaveTable = waveTable

        DispatchQueue.global(qos: .userInteractive).async { [weak self] in
            guard let self else { return }
            let frame = WavelengthRenderer.renderToImage(
                size: renderSize, scale: 2.0,
                time: renderTime, speakingTime: renderSpeakingTime,
                params: renderParams, particles: &renderParticles,
                textures: self.textures, waveScale: renderWaveScale,
                waveTable: renderWaveTable
            )
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.particles = renderParticles
                self.renderedFrame = frame
                self.isRendering = false
            }
        }
    }
}

// MARK: - Previews

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
#endif
