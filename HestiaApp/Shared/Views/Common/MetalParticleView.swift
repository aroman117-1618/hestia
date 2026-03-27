// MetalParticleView.swift
// HestiaApp
//
// Metal-accelerated particle renderer for the wavelength animation.
// Non-actor-isolated — owns particle state and renders on Metal's display link thread.
// UIViewRepresentable wraps MTKView for SwiftUI integration.
// Triple-buffer ring prevents CPU/GPU contention.

#if os(iOS)
import SwiftUI
import MetalKit

// MARK: - GPU Data Structures

/// Per-particle data uploaded to the GPU each frame.
/// Must match ParticleInstance in Particles.metal exactly.
struct ParticleGPUData {
    var position: SIMD2<Float> = .zero
    var size: Float = 0
    var alpha: Float = 0
    var texIndex: UInt32 = 0
    var _pad: UInt32 = 0  // Pad to 24 bytes (Metal struct alignment)
}

struct ParticleUniforms {
    var viewportSize: SIMD2<Float> = .zero
}

// MARK: - Metal Particle Renderer

/// Owns particle state and Metal resources. Called from MTKView's display link thread.
/// Not @MainActor — avoids threading conflict with MTKViewDelegate.draw().
final class MetalParticleRenderer: NSObject, MTKViewDelegate {

    // Metal resources
    private let device: MTLDevice
    private let commandQueue: MTLCommandQueue
    private let pipelineState: MTLRenderPipelineState
    private let textureArray: MTLTexture

    // Triple-buffer ring
    private let maxParticles = 2000
    private var instanceBuffers: [MTLBuffer] = []
    private let bufferSemaphore = DispatchSemaphore(value: 3)
    private var bufferIndex = 0

    // Particle state (owned by renderer, not @MainActor)
    private var particles: [Particle] = []
    private var waveTable = WaveTable()
    private var currentParams: WavelengthParams?
    private var globalTime: Double = 0
    private var speakingTime: Double = 0
    private var lastTimestamp: TimeInterval = 0
    private var initialized = false

    // Inputs (set from main thread, read from render thread)
    private let lock = NSLock()
    private var _mode: WavelengthMode = .idle
    private var _audioLevel: CGFloat = 0
    private var _waveScale: CGFloat = 1.0
    private var _viewportSize: CGSize = .zero

    var mode: WavelengthMode {
        get { lock.withLock { _mode } }
        set { lock.withLock { _mode = newValue } }
    }
    var audioLevel: CGFloat {
        get { lock.withLock { _audioLevel } }
        set { lock.withLock { _audioLevel = newValue } }
    }
    var waveScale: CGFloat {
        get { lock.withLock { _waveScale } }
        set { lock.withLock { _waveScale = newValue } }
    }

    // MARK: - Init

    init?(mtkView: MTKView) {
        guard let device = MTLCreateSystemDefaultDevice(),
              let queue = device.makeCommandQueue() else {
            return nil
        }
        self.device = device
        self.commandQueue = queue

        // Load shaders
        guard let library = device.makeDefaultLibrary(),
              let vertexFn = library.makeFunction(name: "particleVertex"),
              let fragmentFn = library.makeFunction(name: "particleFragment") else {
            return nil
        }

        // Pipeline with additive blending
        let desc = MTLRenderPipelineDescriptor()
        desc.vertexFunction = vertexFn
        desc.fragmentFunction = fragmentFn
        desc.colorAttachments[0].pixelFormat = mtkView.colorPixelFormat

        // Additive blending: src * srcAlpha + dst * 1
        desc.colorAttachments[0].isBlendingEnabled = true
        desc.colorAttachments[0].rgbBlendOperation = .add
        desc.colorAttachments[0].alphaBlendOperation = .add
        desc.colorAttachments[0].sourceRGBBlendFactor = .one
        desc.colorAttachments[0].destinationRGBBlendFactor = .one
        desc.colorAttachments[0].sourceAlphaBlendFactor = .one
        desc.colorAttachments[0].destinationAlphaBlendFactor = .one

        do {
            pipelineState = try device.makeRenderPipelineState(descriptor: desc)
        } catch {
            NSLog("[Metal] Pipeline creation failed: %@", error.localizedDescription)
            return nil
        }

        // Create triple-buffer ring
        let bufferSize = MemoryLayout<ParticleGPUData>.stride * maxParticles
        for _ in 0..<3 {
            guard let buffer = device.makeBuffer(length: bufferSize, options: .storageModeShared) else {
                return nil
            }
            instanceBuffers.append(buffer)
        }

        // Create texture array from palette
        textureArray = Self.createTextureArray(device: device)

        super.init()

        // Configure MTKView
        mtkView.device = device
        mtkView.delegate = self
        mtkView.clearColor = MTLClearColor(red: 0, green: 0, blue: 0, alpha: 1)  // Opaque black — matches black background
        mtkView.colorPixelFormat = .bgra8Unorm
        mtkView.framebufferOnly = true
        mtkView.isPaused = false
        mtkView.enableSetNeedsDisplay = false
        mtkView.preferredFramesPerSecond = 60
        mtkView.isOpaque = false
        mtkView.layer.isOpaque = false
        mtkView.backgroundColor = .clear

        // Initialize particles
        initializeParticles()
    }

    private func initializeParticles() {
        particles.reserveCapacity(maxParticles)
        for _ in 0..<maxParticles {
            particles.append(Particle.create(width: 390, height: 844))
        }
        initialized = true
        NSLog("[Metal] Initialized: %d particles, texture array ready", particles.count)
    }

    // MARK: - Texture Array

    private static func createTextureArray(device: MTLDevice) -> MTLTexture {
        let size = 64  // Use 64x64 for all (GPU doesn't care about small textures)
        let count = WavelengthPalette.count * 2  // 7 colors × 2 (normal + hero)

        let desc = MTLTextureDescriptor()
        desc.textureType = .type2DArray
        desc.pixelFormat = .rgba8Unorm
        desc.width = size
        desc.height = size
        desc.arrayLength = count
        desc.usage = .shaderRead

        let texture = device.makeTexture(descriptor: desc)!

        for (i, color) in WavelengthPalette.colors.enumerated() {
            // Normal texture (index i*2)
            let normalData = generateRadialGradient(
                r: color.r, g: color.g, b: color.b,
                size: size, isHero: false
            )
            texture.replace(
                region: MTLRegion(origin: .init(x: 0, y: 0, z: 0),
                                  size: .init(width: size, height: size, depth: 1)),
                mipmapLevel: 0, slice: i * 2,
                withBytes: normalData,
                bytesPerRow: size * 4,
                bytesPerImage: size * size * 4
            )

            // Hero texture (index i*2 + 1)
            let heroData = generateRadialGradient(
                r: color.r, g: color.g, b: color.b,
                size: size, isHero: true
            )
            texture.replace(
                region: MTLRegion(origin: .init(x: 0, y: 0, z: 0),
                                  size: .init(width: size, height: size, depth: 1)),
                mipmapLevel: 0, slice: i * 2 + 1,
                withBytes: heroData,
                bytesPerRow: size * 4,
                bytesPerImage: size * size * 4
            )
        }

        return texture
    }

    private static func generateRadialGradient(
        r: CGFloat, g: CGFloat, b: CGFloat,
        size: Int, isHero: Bool
    ) -> [UInt8] {
        var pixels = [UInt8](repeating: 0, count: size * size * 4)
        let center = Float(size) / 2.0
        let maxDist = center

        // Tighter stops for sharper particles
        let stop1: Float = isHero ? 0.12 : 0.06
        let stop2: Float = isHero ? 0.30 : 0.18
        let stop3: Float = isHero ? 0.60 : 0.40

        for y in 0..<size {
            for x in 0..<size {
                let dx = Float(x) - center + 0.5
                let dy = Float(y) - center + 0.5
                let dist = sqrt(dx * dx + dy * dy) / maxDist
                let t = min(dist, 1.0)

                // Interpolate alpha based on gradient stops
                var alpha: Float
                if t <= stop1 {
                    alpha = 1.0 - (1.0 - 0.9) * (t / stop1)
                } else if t <= stop2 {
                    alpha = 0.9 - (0.9 - 0.3) * ((t - stop1) / (stop2 - stop1))
                } else if t <= stop3 {
                    alpha = 0.3 - (0.3 - 0.05) * ((t - stop2) / (stop3 - stop2))
                } else {
                    alpha = 0.05 * (1.0 - (t - stop3) / (1.0 - stop3))
                }
                alpha = max(0, alpha)

                let idx = (y * size + x) * 4
                pixels[idx + 0] = UInt8(min(Float(r) * 255 * alpha, 255))  // R premultiplied
                pixels[idx + 1] = UInt8(min(Float(g) * 255 * alpha, 255))  // G premultiplied
                pixels[idx + 2] = UInt8(min(Float(b) * 255 * alpha, 255))  // B premultiplied
                pixels[idx + 3] = UInt8(min(alpha * 255, 255))              // A
            }
        }
        return pixels
    }

    // MARK: - MTKViewDelegate

    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {
        lock.withLock { _viewportSize = size }
    }

    func draw(in view: MTKView) {
        guard initialized else { return }

        // Read inputs
        let currentMode = mode
        let currentWaveScale = waveScale
        let viewSize = lock.withLock { _viewportSize }
        guard viewSize.width > 0 else { return }

        // Wait for available buffer
        _ = bufferSemaphore.wait(timeout: .now() + 0.016)

        // Update timing
        let now = CACurrentMediaTime()
        let dt = lastTimestamp == 0 ? 0.016 : min(0.033, now - lastTimestamp)
        lastTimestamp = now

        // Lerp params
        let target = WavelengthParams.target(for: currentMode)
        if let current = currentParams {
            currentParams = current.lerped(toward: target, alpha: 0.05)
        } else {
            currentParams = target
        }
        guard let params = currentParams else { return }

        globalTime += 0.005 * params.speedMult
        speakingTime += dt * (1 + params.audioVol * 4)

        // Pre-compute wave tables
        waveTable.compute(time: globalTime, speakingTime: speakingTime)

        // Viewport in points (not pixels)
        let width = viewSize.width / view.contentScaleFactor
        let height = viewSize.height / view.contentScaleFactor
        let centerY = height * 0.54  // Wave at ~27% of full screen = ~54% of the 50% frame

        let active = params.audioVol
        let glow = params.glowMult
        let wScale = Double(currentWaveScale)
        let visibleCount = min(Int(Double(maxParticles) * 0.66 * params.densityMult), particles.count)

        let baseAmps: [Double] = [35, 40, 45]
        let asymmetries: [Double] = [1.3, 1.7, 2.2]
        let troughDamps: [Double] = [0.5, 0.3, 0.15]
        let bucketCount = Double(WaveTable.bucketCount)

        // Fill instance buffer
        let buffer = instanceBuffers[bufferIndex]
        let gpuData = buffer.contents().bindMemory(to: ParticleGPUData.self, capacity: maxParticles)
        var gpuCount = 0

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

            // Taper
            let distFromCenter = abs(normalizedX - 0.5) * 2.2
            let taper = max(0, 1 - distFromCenter * distFromCenter)
            let alpha = taper * p.z
            if alpha <= 0.05 { continue }

            // Wave table lookup
            let bucket = min(Int(normalizedX * bucketCount), WaveTable.bucketCount - 1)
            let ribbon = p.ribbon
            let tableIdx = bucket * 3 + ribbon

            var calmY = waveTable.calm[tableIdx]
            calmY += sin(p.phaseOffset + globalTime) * 8
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

            var waveY = calmY * (1.0 - active) + speakingY * active
            let finalThickness = 1.0 * (1.0 - active) + speakingThicknessMap * active
            let swirl = sin(p.phaseOffset + speakingTime * 2.5) * (15 * active)
            let currentYOffset = (p.yOffset + swirl) * finalThickness
            waveY *= taper
            let y = Double(centerY) + (waveY * wScale) + (currentYOffset * p.z * taper * wScale)

            let particleSize = p.baseSize * p.z
            let drawSize = particleSize * 6

            gpuData[gpuCount] = ParticleGPUData(
                position: SIMD2<Float>(Float(p.x), Float(y)),
                size: Float(drawSize),
                alpha: Float(alpha * glow),
                texIndex: UInt32(p.colorIdx * 2 + (p.isHero ? 1 : 0))
            )
            gpuCount += 1
        }

        // Render
        guard let drawable = view.currentDrawable,
              let passDesc = view.currentRenderPassDescriptor,
              let cmdBuffer = commandQueue.makeCommandBuffer(),
              let encoder = cmdBuffer.makeRenderCommandEncoder(descriptor: passDesc) else {
            bufferSemaphore.signal()
            return
        }

        var uniforms = ParticleUniforms(
            viewportSize: SIMD2<Float>(Float(width), Float(height))
        )

        encoder.setRenderPipelineState(pipelineState)
        encoder.setVertexBuffer(buffer, offset: 0, index: 0)
        encoder.setVertexBytes(&uniforms, length: MemoryLayout<ParticleUniforms>.size, index: 1)
        encoder.setFragmentTexture(textureArray, index: 0)

        // Draw instanced quads (6 vertices per quad, gpuCount instances)
        encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 6, instanceCount: gpuCount)
        encoder.endEncoding()

        cmdBuffer.present(drawable)

        let semaphore = bufferSemaphore
        cmdBuffer.addCompletedHandler { _ in
            semaphore.signal()
        }
        cmdBuffer.commit()

        bufferIndex = (bufferIndex + 1) % 3
    }

    // MARK: - Lifecycle

    func pause() {
        // Called when view disappears (tab switch)
    }

    func resume(width: Double, height: Double) {
        // Re-seed particles if needed
        if particles.isEmpty {
            initializeParticles()
        }
    }
}

// MARK: - SwiftUI Wrapper

struct MetalParticleView: UIViewRepresentable {
    let mode: WavelengthMode
    var audioLevel: CGFloat = 0
    var waveScale: CGFloat = 1.0

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> MTKView {
        let mtkView = MTKView()
        mtkView.backgroundColor = .clear
        mtkView.isOpaque = false

        if let renderer = MetalParticleRenderer(mtkView: mtkView) {
            context.coordinator.renderer = renderer
        } else {
            NSLog("[Metal] Failed to create renderer — Metal unavailable")
        }

        return mtkView
    }

    func updateUIView(_ mtkView: MTKView, context: Context) {
        context.coordinator.renderer?.mode = mode
        context.coordinator.renderer?.audioLevel = audioLevel
        context.coordinator.renderer?.waveScale = waveScale
    }

    static func dismantleUIView(_ uiView: MTKView, coordinator: Coordinator) {
        uiView.isPaused = true
        coordinator.renderer = nil
    }

    class Coordinator {
        var renderer: MetalParticleRenderer?
    }
}
#endif
