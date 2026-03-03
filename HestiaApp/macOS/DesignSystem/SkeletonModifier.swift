import SwiftUI

// MARK: - Shimmer Effect

/// Animated shimmer overlay for skeleton loading states.
/// Usage: `.shimmer()` on any placeholder shape.
struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        content
            .overlay {
                GeometryReader { geo in
                    LinearGradient(
                        stops: [
                            .init(color: .clear, location: max(0, phase - 0.3)),
                            .init(color: .white.opacity(0.12), location: phase),
                            .init(color: .clear, location: min(1, phase + 0.3))
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                }
                .mask(content)
            }
            .onAppear {
                withAnimation(
                    .linear(duration: 1.4)
                    .repeatForever(autoreverses: false)
                ) {
                    phase = 2
                }
            }
    }
}

extension View {
    /// Apply a shimmer animation — use on skeleton placeholder shapes.
    func shimmer() -> some View {
        modifier(ShimmerModifier())
    }
}
