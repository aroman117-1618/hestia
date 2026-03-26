// HestiaHeaderView.swift
// HestiaApp
//
// Amber gradient title with constellation stars and shimmer underline.
// Sits at top of conversation view above the wavelength.

import SwiftUI

/// Animated "Hestia" header — gradient amber title, twinkling constellation stars,
/// and a breathing shimmer underline.
struct HestiaHeaderView: View {
    @State private var shimmerWidth: CGFloat = 60
    @State private var starPhases: [Bool] = Array(repeating: false, count: 7)

    var body: some View {
        ZStack {
            // Constellation stars
            constellationStars

            VStack(spacing: 6) {
                // Gradient amber title
                Text("Hestia")
                    .font(.system(size: 22, weight: .bold))
                    .tracking(1.5)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [
                                Color(red: 1, green: 215/255, blue: 0),       // #FFD700
                                Color(red: 1, green: 159/255, blue: 10/255),  // #FF9F0A
                                Color(red: 224/255, green: 138/255, blue: 0), // #E08A00
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                // Shimmer underline
                RoundedRectangle(cornerRadius: 1)
                    .fill(
                        LinearGradient(
                            colors: [
                                .clear,
                                Color(red: 1, green: 159/255, blue: 10/255).opacity(0.8),
                                Color(red: 1, green: 215/255, blue: 0),
                                Color(red: 1, green: 159/255, blue: 10/255).opacity(0.8),
                                .clear,
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: shimmerWidth, height: 1.5)
            }
        }
        .frame(width: 200, height: 60)
        .onAppear {
            withAnimation(.easeInOut(duration: 3).repeatForever(autoreverses: true)) {
                shimmerWidth = 100
            }
            // Stagger star twinkle animations
            for i in 0..<starPhases.count {
                let delay = Double(i) * 0.35
                withAnimation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true).delay(delay)) {
                    starPhases[i] = true
                }
            }
        }
    }

    // MARK: - Constellation Stars

    private var constellationStars: some View {
        ZStack {
            starDot(x: 0.05, y: 0.0, size: 2, index: 0)
            starDot(x: 0.90, y: 0.15, size: 3, index: 1)
            starDot(x: 0.15, y: 0.85, size: 2, index: 2)
            starDot(x: 0.55, y: 0.10, size: 3, index: 3)
            starDot(x: 0.80, y: 0.75, size: 4, index: 4)
            starDot(x: 0.00, y: 0.45, size: 2, index: 5)
            starDot(x: 0.95, y: 0.60, size: 3, index: 6)
        }
    }

    private func starDot(x: CGFloat, y: CGFloat, size: CGFloat, index: Int) -> some View {
        GeometryReader { geo in
            Circle()
                .fill(Color(red: 1, green: 215/255, blue: 0))  // #FFD700
                .frame(width: size, height: size)
                .shadow(color: Color(red: 1, green: 159/255, blue: 10/255).opacity(0.6), radius: size)
                .opacity(starPhases[index] ? 1.0 : 0.2)
                .scaleEffect(starPhases[index] ? 1.3 : 0.7)
                .position(x: geo.size.width * x, y: geo.size.height * y)
        }
    }
}

#if DEBUG
#Preview("Hestia Header") {
    ZStack {
        Color(red: 2/255, green: 1/255, blue: 1/255)
        HestiaHeaderView()
    }
}
#endif
