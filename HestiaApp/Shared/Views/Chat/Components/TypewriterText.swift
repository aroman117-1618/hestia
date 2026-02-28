import SwiftUI
import HestiaShared
import Combine

/// A text view that displays content character by character
struct TypewriterText: View {
    let text: String
    let speed: Double // seconds per character

    @State private var displayedText = ""
    @State private var currentIndex = 0
    @State private var timer: Timer?

    var body: some View {
        Text(displayedText)
            .onAppear {
                startTyping()
            }
            .onDisappear {
                stopTyping()
            }
            .onChange(of: text) { newText in
                // Reset if text changes
                displayedText = ""
                currentIndex = 0
                startTyping()
            }
    }

    private func startTyping() {
        stopTyping()

        timer = Timer.scheduledTimer(withTimeInterval: speed, repeats: true) { _ in
            if currentIndex < text.count {
                let index = text.index(text.startIndex, offsetBy: currentIndex)
                displayedText.append(text[index])
                currentIndex += 1
            } else {
                stopTyping()
            }
        }
    }

    private func stopTyping() {
        timer?.invalidate()
        timer = nil
    }
}

// MARK: - Typewriter Container

/// Container that wraps typewriter effect with styling
struct TypewriterContainer: View {
    let text: String
    let speed: Double
    let onComplete: (() -> Void)?

    @State private var isComplete = false

    init(text: String, speed: Double = 0.03, onComplete: (() -> Void)? = nil) {
        self.text = text
        self.speed = speed
        self.onComplete = onComplete
    }

    var body: some View {
        TypewriterTextWithCallback(
            text: text,
            speed: speed,
            onComplete: {
                isComplete = true
                onComplete?()
            }
        )
        .font(.messageBody)
        .foregroundColor(.white)
        .padding(Spacing.md)
        .background(Color.assistantBubbleBackground)
        .cornerRadius(CornerRadius.standard)
    }
}

/// Typewriter with completion callback
struct TypewriterTextWithCallback: View {
    let text: String
    let speed: Double
    let onComplete: () -> Void

    @State private var displayedText = ""
    @State private var currentIndex = 0

    var body: some View {
        Text(displayedText)
            .onAppear {
                animateText()
            }
    }

    private func animateText() {
        guard currentIndex < text.count else {
            onComplete()
            return
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + speed) {
            let index = text.index(text.startIndex, offsetBy: currentIndex)
            displayedText.append(text[index])
            currentIndex += 1
            animateText()
        }
    }
}

// MARK: - Preview

struct TypewriterText_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 20) {
                TypewriterText(
                    text: "Hi Boss, ready for some good trouble?",
                    speed: 0.05
                )
                .font(.messageBody)
                .foregroundColor(.white)

                TypewriterContainer(
                    text: "This is a longer message to demonstrate the typewriter effect working properly.",
                    speed: 0.03
                )
            }
            .padding()
        }
    }
}
