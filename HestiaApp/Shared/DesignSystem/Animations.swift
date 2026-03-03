import SwiftUI

extension Animation {
    // MARK: - Hestia Personality Animations

    /// Standard Hestia animation - snappy but smooth
    static let hestiaStandard = Animation.spring(response: 0.3, dampingFraction: 0.7)

    /// Quick transitions - mode switches, UI updates
    static let hestiaQuick = Animation.spring(response: 0.2, dampingFraction: 0.8)

    /// Slow, deliberate - for dramatic moments
    static let hestiaSlow = Animation.spring(response: 0.5, dampingFraction: 0.6)

    // MARK: - Specific Use Cases

    /// Message appearance - typewriter then slide up
    static let messageAppear = Animation.spring(response: 0.35, dampingFraction: 0.75)

    /// Mode switch ripple effect
    static let modeSwitch = Animation.spring(response: 0.6, dampingFraction: 0.65)

    /// Error shake
    static let errorShake = Animation.spring(response: 0.2, dampingFraction: 0.3)

    /// Loading pulse
    static let loadingPulse = Animation.easeInOut(duration: 1.0).repeatForever(autoreverses: true)

    // MARK: - macOS UX Polish Springs

    /// Navigation view switch — smooth lateral slide with slight overshoot
    static let hestiaNavSwitch = Animation.spring(response: 0.3, dampingFraction: 0.75)

    /// Panel open/close — slightly slower, controlled
    static let hestiaPanel = Animation.spring(response: 0.35, dampingFraction: 0.8)

    /// Hover feedback — snappy, no overshoot
    static let hestiaHover = Animation.spring(response: 0.15, dampingFraction: 0.9)

    /// Sidebar indicator slide — smooth tracking between nav items
    static let hestiaIndicator = Animation.spring(response: 0.4, dampingFraction: 0.8)
}

// MARK: - View Modifiers

/// Ripple effect modifier for mode transitions
struct RippleEffect: ViewModifier {
    let origin: CGPoint
    let trigger: Bool

    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geometry in
                    if trigger {
                        Circle()
                            .fill(Color.white.opacity(0.2))
                            .frame(width: 0, height: 0)
                            .position(origin)
                            .modifier(RippleAnimation())
                    }
                }
            )
    }
}

/// Internal ripple animation
struct RippleAnimation: ViewModifier {
    @State private var scale: CGFloat = 0
    @State private var opacity: Double = 1

    func body(content: Content) -> some View {
        content
            .scaleEffect(scale)
            .opacity(opacity)
            .onAppear {
                withAnimation(.modeSwitch) {
                    scale = 50
                    opacity = 0
                }
            }
    }
}

/// Message appearance animation modifier
struct MessageAppearAnimation: ViewModifier {
    let delay: Double
    @State private var isVisible = false

    func body(content: Content) -> some View {
        content
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 20)
            .onAppear {
                withAnimation(.messageAppear.delay(delay)) {
                    isVisible = true
                }
            }
    }
}

/// Shake animation for errors
struct ShakeEffect: ViewModifier {
    let trigger: Bool
    @State private var offset: CGFloat = 0

    func body(content: Content) -> some View {
        content
            .offset(x: offset)
            .onChange(of: trigger) { newValue in
                if newValue {
                    withAnimation(.errorShake) {
                        offset = 10
                    }
                    withAnimation(.errorShake.delay(0.1)) {
                        offset = -8
                    }
                    withAnimation(.errorShake.delay(0.2)) {
                        offset = 6
                    }
                    withAnimation(.errorShake.delay(0.3)) {
                        offset = -4
                    }
                    withAnimation(.errorShake.delay(0.4)) {
                        offset = 0
                    }
                }
            }
    }
}

/// Loading pulse animation
struct PulseAnimation: ViewModifier {
    @State private var isPulsing = false

    func body(content: Content) -> some View {
        content
            .opacity(isPulsing ? 0.5 : 1.0)
            .onAppear {
                withAnimation(.loadingPulse) {
                    isPulsing = true
                }
            }
    }
}

/// Expanding ripple effect for mode switch transitions
struct ExpandingRipple: ViewModifier {
    @State private var scale: CGFloat = 1
    @State private var opacity: Double = 1

    func body(content: Content) -> some View {
        content
            .scaleEffect(scale)
            .opacity(opacity)
            .onAppear {
                withAnimation(.easeOut(duration: 0.6)) {
                    scale = 100
                    opacity = 0
                }
            }
    }
}

// MARK: - View Extensions

extension View {
    /// Apply ripple effect on mode transition
    func rippleEffect(at origin: CGPoint, trigger: Bool) -> some View {
        self.modifier(RippleEffect(origin: origin, trigger: trigger))
    }

    /// Apply message appearance animation
    func messageAppearAnimation(delay: Double = 0) -> some View {
        self.modifier(MessageAppearAnimation(delay: delay))
    }

    /// Apply shake effect on error
    func shakeOnError(_ trigger: Bool) -> some View {
        self.modifier(ShakeEffect(trigger: trigger))
    }

    /// Apply loading pulse animation
    func pulseAnimation() -> some View {
        self.modifier(PulseAnimation())
    }

    /// Apply expanding ripple animation
    func expandingRipple() -> some View {
        self.modifier(ExpandingRipple())
    }
}
