import SwiftUI

/// Animated waveform bars that respond to audio level input.
/// Used in the ChatInputBar during active voice recording.
struct WaveformView: View {
    let audioLevel: CGFloat
    let tintColor: Color
    let barCount: Int

    init(audioLevel: CGFloat, tintColor: Color, barCount: Int = 9) {
        self.audioLevel = audioLevel
        self.tintColor = tintColor
        self.barCount = barCount
    }

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<barCount, id: \.self) { index in
                WaveformBar(
                    audioLevel: audioLevel,
                    barIndex: index,
                    barCount: barCount,
                    tintColor: tintColor
                )
            }
        }
    }
}

/// Individual animated bar in the waveform.
private struct WaveformBar: View {
    let audioLevel: CGFloat
    let barIndex: Int
    let barCount: Int
    let tintColor: Color

    @State private var idlePhase: CGFloat = 0

    /// Height scale: center bars are taller, edges shorter (bell curve shape)
    private var positionScale: CGFloat {
        let center = CGFloat(barCount) / 2.0
        let distance = abs(CGFloat(barIndex) - center) / center
        return 1.0 - (distance * 0.5)
    }

    /// Final bar height combining audio level + idle animation + position
    private var barHeight: CGFloat {
        let minHeight: CGFloat = 4
        let maxHeight: CGFloat = 24
        let idleOffset = sin(idlePhase + CGFloat(barIndex) * 0.7) * 0.15
        let level = max(audioLevel + idleOffset, 0.1)
        let height = minHeight + (maxHeight - minHeight) * level * positionScale
        return height
    }

    var body: some View {
        RoundedRectangle(cornerRadius: 1.5)
            .fill(tintColor)
            .frame(width: 3, height: barHeight)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: audioLevel)
            .onAppear {
                // Subtle idle animation
                withAnimation(.linear(duration: 2.0).repeatForever(autoreverses: false)) {
                    idlePhase = .pi * 2
                }
            }
    }
}
