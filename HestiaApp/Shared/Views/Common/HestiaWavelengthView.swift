// HestiaWavelengthView.swift
// HestiaApp

import SwiftUI

// MARK: - ViewModel

@MainActor
final class WavelengthViewModel: ObservableObject {
    @Published var renderedFrame: CGImage?

    private var currentParams: WavelengthParams?
    private var globalTime: Double = 0
    private var lastTimestamp: TimeInterval = 0

    func update(date: Date, mode: WavelengthMode, audioLevel: CGFloat, size: CGSize) {
        let now = date.timeIntervalSinceReferenceDate
        let dt = lastTimestamp == 0 ? 0.016 : min(0.033, now - lastTimestamp)
        lastTimestamp = now
        globalTime += dt

        let level = Double(audioLevel)
        let target = WavelengthParams.target(for: mode, level: level, time: globalTime)
        let alpha = min(max(dt * 4.0, 0), 1)

        if let current = currentParams {
            currentParams = current.lerped(toward: target, alpha: alpha)
        } else {
            currentParams = target
        }

        guard let p = currentParams else { return }

        #if os(iOS)
        let displayScale = UIScreen.main.scale
        #else
        let displayScale: CGFloat = NSScreen.main?.backingScaleFactor ?? 2.0
        #endif

        renderedFrame = WavelengthRenderer.renderToImage(
            size: size, scale: displayScale,
            time: globalTime, params: p
        )
    }
}

// MARK: - View

struct HestiaWavelengthView: View {
    let mode: WavelengthMode
    var size: CGFloat = 320
    var audioLevel: CGFloat = 0.0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @StateObject private var viewModel = WavelengthViewModel()

    private var frameInterval: Double {
        mode == .idle ? 1.0 / 20.0 : 1.0 / 30.0
    }

    private var renderSize: CGSize {
        CGSize(width: size * 1.6, height: size * 1.6)
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
        TimelineView(.animation(minimumInterval: frameInterval)) { timeline in
            let _ = viewModel.update(
                date: timeline.date,
                mode: mode,
                audioLevel: audioLevel,
                size: renderSize
            )

            if let cgImage = viewModel.renderedFrame {
                #if os(iOS)
                let displayScale = UIScreen.main.scale
                #else
                let displayScale: CGFloat = NSScreen.main?.backingScaleFactor ?? 2.0
                #endif

                Image(cgImage, scale: displayScale, label: Text("Hestia wavelength"))
                    .frame(width: renderSize.width, height: renderSize.height)
            } else {
                Color.clear
                    .frame(width: renderSize.width, height: renderSize.height)
            }
        }
    }

    // MARK: - Static Fallback (Reduce Motion)

    private var staticFallback: some View {
        Circle()
            .fill(
                RadialGradient(
                    colors: [
                        Color(red: 1, green: 159.0/255.0, blue: 10.0/255.0).opacity(0.3),
                        Color(red: 80.0/255.0, green: 40.0/255.0, blue: 0).opacity(0.15),
                        .clear
                    ],
                    center: .center,
                    startRadius: 0,
                    endRadius: size / 2
                )
            )
            .frame(width: size, height: size)
            .overlay(
                Circle()
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color(red: 1, green: 179.0/255.0, blue: 71.0/255.0).opacity(0.4),
                                Color(red: 1, green: 159.0/255.0, blue: 10.0/255.0).opacity(0.2)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 2
                    )
            )
    }
}

#if DEBUG
#Preview("Wavelength - Idle") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .idle, size: 200)
    }
}

#Preview("Wavelength - Speaking") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .speaking, size: 200, audioLevel: 0.6)
    }
}
#endif
