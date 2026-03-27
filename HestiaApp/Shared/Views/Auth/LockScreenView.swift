import SwiftUI
import HestiaShared

/// Lock screen — amber gradient Hestia title with firefly glow,
/// Face ID circle, and authenticate button. Pure black background.
struct LockScreenView: View {
    @EnvironmentObject var authService: AuthService
    @State private var isLoading = false
    @State private var error: HestiaError?
    @State private var showError = false
    @State private var shimmerScale: CGFloat = 0.6
    @State private var starPhases: [Bool] = Array(repeating: false, count: 5)
    @State private var emberBreathing = false

    let onUnlock: () -> Void

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Hestia title with firefly glow behind
                ZStack {
                    // Firefly glow
                    RadialGradient(
                        colors: [
                            Color(red: 1, green: 159/255, blue: 10/255).opacity(0.2),
                            Color(red: 1, green: 159/255, blue: 10/255).opacity(0.06),
                            .clear
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: 100
                    )
                    .frame(width: 200, height: 80)

                    // Firefly dots
                    fireflyDots

                    // Title + underline
                    VStack(spacing: 8) {
                        Text("Hestia")
                            .font(.system(size: 28, weight: .bold))
                            .tracking(2)
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [
                                        Color(red: 1, green: 215/255, blue: 0),
                                        Color(red: 1, green: 159/255, blue: 10/255),
                                    ],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )

                        // Shimmer underline (scaleX, not width — no layout shift)
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
                            .frame(width: 100, height: 1.5)
                            .scaleEffect(x: shimmerScale, y: 1)
                    }
                }

                Spacer()
                    .frame(height: 50)

                // Face ID ember circle
                ZStack {
                    Circle()
                        .fill(
                            RadialGradient(
                                colors: [
                                    Color(red: 1, green: 159/255, blue: 10/255).opacity(0.12),
                                    .clear
                                ],
                                center: .center,
                                startRadius: 0,
                                endRadius: 40
                            )
                        )
                        .frame(width: 80, height: 80)
                        .overlay(
                            Circle()
                                .stroke(Color(red: 1, green: 159/255, blue: 10/255).opacity(0.15), lineWidth: 1)
                        )
                        .scaleEffect(emberBreathing ? 1.05 : 1.0)

                    Image(systemName: "faceid")
                        .font(.system(size: 28))
                        .foregroundColor(Color(red: 1, green: 159/255, blue: 10/255).opacity(0.65))
                }

                Spacer()

                // Authenticate button
                Button {
                    Task { await authenticate() }
                } label: {
                    HStack(spacing: Spacing.sm) {
                        if isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: Color(red: 1, green: 159/255, blue: 10/255)))
                        } else {
                            Image(systemName: authService.biometricType != .none ? authService.biometricType.iconName : "lock.open.fill")
                                .font(.system(size: 20))
                        }
                        Text("Authenticate")
                            .font(.system(size: 17, weight: .semibold))
                    }
                    .foregroundColor(Color(red: 1, green: 159/255, blue: 10/255))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(
                        RoundedRectangle(cornerRadius: 14)
                            .fill(
                                LinearGradient(
                                    colors: [
                                        Color(red: 1, green: 159/255, blue: 10/255).opacity(0.2),
                                        Color(red: 1, green: 159/255, blue: 10/255).opacity(0.1),
                                    ],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(Color(red: 1, green: 159/255, blue: 10/255).opacity(0.3), lineWidth: 1)
                            )
                    )
                }
                .disabled(isLoading)
                .padding(.horizontal, 40)
                .padding(.bottom, 60)
            }
        }
        .alert("Authentication Failed", isPresented: $showError) {
            Button("Try Again") {
                showError = false
                error = nil
            }
        } message: {
            Text(error?.userMessage ?? "Please try again")
        }
        .onAppear {
            // Animations
            withAnimation(.easeInOut(duration: 3).repeatForever(autoreverses: true)) {
                shimmerScale = 1.0
            }
            withAnimation(.easeInOut(duration: 3).repeatForever(autoreverses: true)) {
                emberBreathing = true
            }
            for i in 0..<starPhases.count {
                withAnimation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true).delay(Double(i) * 0.4)) {
                    starPhases[i] = true
                }
            }
            // Auth only on button tap — no auto-trigger
        }
        .onChange(of: authService.isAuthenticated) { newValue in
            if newValue { onUnlock() }
        }
    }

    // MARK: - Firefly Dots

    private var fireflyDots: some View {
        ZStack {
            fireflyDot(x: 0.1, y: 0.15, index: 0)
            fireflyDot(x: 0.85, y: 0.7, index: 1)
            fireflyDot(x: 0.9, y: 0.25, index: 2)
            fireflyDot(x: 0.2, y: 0.8, index: 3)
            fireflyDot(x: 0.5, y: 0.4, index: 4)
        }
        .frame(width: 220, height: 100)
    }

    private func fireflyDot(x: CGFloat, y: CGFloat, index: Int) -> some View {
        GeometryReader { geo in
            Circle()
                .fill(Color(red: 1, green: 215/255, blue: 0))
                .frame(width: 3, height: 3)
                .shadow(color: Color(red: 1, green: 215/255, blue: 0).opacity(0.5), radius: 3)
                .opacity(starPhases[index] ? 0.9 : 0.2)
                .scaleEffect(starPhases[index] ? 1.3 : 0.7)
                .position(x: geo.size.width * x, y: geo.size.height * y)
        }
    }

    // MARK: - Auth

    private func authenticate() async {
        isLoading = true
        error = nil

        do {
            try await authService.authenticate()
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }
}

struct LockScreenView_Previews: PreviewProvider {
    static var previews: some View {
        LockScreenView(onUnlock: {})
            .environmentObject(AuthService())
    }
}
