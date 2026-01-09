import SwiftUI

/// Loading indicator with animated dots
struct LoadingView: View {
    @State private var animatingDots = false

    var body: some View {
        HStack(spacing: 6) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.white.opacity(0.7))
                    .frame(width: 8, height: 8)
                    .offset(y: animatingDots ? -5 : 0)
                    .animation(
                        .easeInOut(duration: 0.5)
                            .repeatForever()
                            .delay(Double(index) * 0.15),
                        value: animatingDots
                    )
            }
        }
        .onAppear {
            animatingDots = true
        }
    }
}

/// Loading indicator styled as a message bubble
struct LoadingBubble: View {
    var body: some View {
        HStack {
            LoadingView()
                .padding(Spacing.md)
                .background(Color.assistantBubbleBackground)
                .cornerRadius(CornerRadius.standard)

            Spacer()
        }
        .padding(.horizontal, Spacing.md)
    }
}

/// Full-screen loading overlay
struct LoadingOverlay: View {
    let message: String?

    init(message: String? = nil) {
        self.message = message
    }

    var body: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: Spacing.md) {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(1.5)

                if let message = message {
                    Text(message)
                        .font(.subheadline)
                        .foregroundColor(.white)
                }
            }
            .padding(Spacing.xl)
            .background(Color.black.opacity(0.6))
            .cornerRadius(CornerRadius.standard)
        }
    }
}

/// Skeleton loading placeholder
struct SkeletonView: View {
    @State private var isAnimating = false

    var body: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(
                LinearGradient(
                    colors: [
                        Color.white.opacity(0.1),
                        Color.white.opacity(0.2),
                        Color.white.opacity(0.1)
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .opacity(isAnimating ? 0.6 : 1.0)
            .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: isAnimating)
            .onAppear {
                isAnimating = true
            }
    }
}

// MARK: - Preview

struct LoadingView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 40) {
                LoadingView()

                LoadingBubble()

                SkeletonView()
                    .frame(width: 200, height: 20)
            }
        }
    }
}
