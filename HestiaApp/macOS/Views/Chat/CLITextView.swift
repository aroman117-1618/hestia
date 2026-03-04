import SwiftUI
import AppKit

// MARK: - CLI Text View (NSViewRepresentable)

/// Wraps NSTextView for a CLI-style multi-line input with monospace font,
/// dark background, history recall, and custom key bindings.
struct CLITextView: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String
    var promptChar: String
    var onSend: () -> Void
    var onEscape: () -> Void

    /// Shared history across the lifetime of the input bar
    @Binding var history: [String]
    @Binding var historyIndex: Int?

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = false
        scrollView.hasHorizontalScroller = false
        scrollView.drawsBackground = false
        scrollView.borderType = .noBorder
        scrollView.autohidesScrollers = true

        let textView = CLIInputTextView()
        textView.delegate = context.coordinator
        textView.coordinator = context.coordinator

        // Appearance
        textView.backgroundColor = NSColor(red: 0x1E / 255, green: 0x1E / 255, blue: 0x1E / 255, alpha: 1)
        textView.textColor = NSColor(red: 0xE0 / 255, green: 0xE0 / 255, blue: 0xE0 / 255, alpha: 1)
        textView.insertionPointColor = NSColor(red: 0xE0 / 255, green: 0xA0 / 255, blue: 0x50 / 255, alpha: 1)
        textView.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
        textView.drawsBackground = true

        // Layout
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainerInset = NSSize(width: 8, height: 8)
        textView.isRichText = false
        textView.allowsUndo = true
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.isAutomaticTextReplacementEnabled = false

        // Text container
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(
            width: scrollView.contentSize.width,
            height: CGFloat.greatestFiniteMagnitude
        )

        scrollView.documentView = textView
        context.coordinator.textView = textView

        // Set initial placeholder
        context.coordinator.updatePlaceholder()

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? CLIInputTextView else { return }

        // Sync text from SwiftUI to NSTextView (avoid loop)
        if textView.string != text && !context.coordinator.isUpdating {
            context.coordinator.isUpdating = true
            textView.string = text
            context.coordinator.isUpdating = false
            context.coordinator.updatePlaceholder()
        }

        // Update coordinator references
        context.coordinator.parent = self
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: CLITextView
        weak var textView: CLIInputTextView?
        var isUpdating = false

        // Placeholder layer
        private var placeholderField: NSTextField?

        init(_ parent: CLITextView) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard !isUpdating, let textView = textView else { return }
            isUpdating = true
            parent.text = textView.string
            isUpdating = false
            updatePlaceholder()
        }

        func updatePlaceholder() {
            guard let textView = textView else { return }

            if textView.string.isEmpty {
                if placeholderField == nil {
                    let field = NSTextField(labelWithString: "")
                    field.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
                    field.textColor = NSColor(red: 0xE0 / 255, green: 0xE0 / 255, blue: 0xE0 / 255, alpha: 0.35)
                    field.isBezeled = false
                    field.drawsBackground = false
                    field.isEditable = false
                    field.isSelectable = false
                    textView.addSubview(field)
                    placeholderField = field
                }
                placeholderField?.stringValue = parent.placeholder
                let inset = textView.textContainerInset
                placeholderField?.frame = NSRect(
                    x: inset.width + 5,
                    y: inset.height,
                    width: textView.bounds.width - inset.width * 2 - 10,
                    height: 20
                )
                placeholderField?.isHidden = false
            } else {
                placeholderField?.isHidden = true
            }
        }

        // MARK: - Key Handling (called from CLIInputTextView)

        func handleKeyDown(_ event: NSEvent, in textView: NSTextView) -> Bool {
            let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)

            // Cmd+Enter → send
            if event.keyCode == 36 && flags.contains(.command) {
                handleSend()
                return true
            }

            // Enter (no modifiers) → send
            if event.keyCode == 36 && flags.isEmpty {
                handleSend()
                return true
            }

            // Shift+Enter → newline (default behavior)
            if event.keyCode == 36 && flags.contains(.shift) {
                return false // Let NSTextView handle it
            }

            // Escape → clear
            if event.keyCode == 53 {
                parent.text = ""
                textView.string = ""
                parent.historyIndex = nil
                updatePlaceholder()
                parent.onEscape()
                return true
            }

            // Up arrow → history recall (only when cursor is on first line)
            if event.keyCode == 126 && flags.isEmpty {
                if isOnFirstLine(textView) && !parent.history.isEmpty {
                    recallPrevious(textView)
                    return true
                }
            }

            // Down arrow → history forward (only when recalling)
            if event.keyCode == 125 && flags.isEmpty {
                if parent.historyIndex != nil {
                    recallNext(textView)
                    return true
                }
            }

            return false
        }

        private func handleSend() {
            let trimmed = parent.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { return }

            // Add to history (max 50)
            parent.history.append(trimmed)
            if parent.history.count > 50 {
                parent.history.removeFirst(parent.history.count - 50)
            }
            parent.historyIndex = nil

            parent.onSend()
        }

        private func isOnFirstLine(_ textView: NSTextView) -> Bool {
            guard let layoutManager = textView.layoutManager,
                  let _ = textView.textContainer else { return true }

            let selectedRange = textView.selectedRange()
            if selectedRange.location == 0 { return true }

            let glyphRange = layoutManager.glyphRange(
                forCharacterRange: NSRange(location: 0, length: selectedRange.location),
                actualCharacterRange: nil
            )

            // Check if we're on the first line fragment
            let firstGlyphRect = layoutManager.lineFragmentRect(forGlyphAt: 0, effectiveRange: nil)
            let cursorGlyphIndex = max(glyphRange.upperBound - 1, 0)
            let currentRect = layoutManager.lineFragmentRect(
                forGlyphAt: cursorGlyphIndex,
                effectiveRange: nil
            )
            return currentRect.minY <= firstGlyphRect.minY
        }

        private func recallPrevious(_ textView: NSTextView) {
            guard !parent.history.isEmpty else { return }

            if let idx = parent.historyIndex {
                let newIdx = max(idx - 1, 0)
                parent.historyIndex = newIdx
                setTextFromHistory(parent.history[newIdx], in: textView)
            } else {
                let lastIdx = parent.history.count - 1
                parent.historyIndex = lastIdx
                setTextFromHistory(parent.history[lastIdx], in: textView)
            }
        }

        private func recallNext(_ textView: NSTextView) {
            guard let idx = parent.historyIndex else { return }

            if idx >= parent.history.count - 1 {
                // Past end of history — clear
                parent.historyIndex = nil
                setTextFromHistory("", in: textView)
            } else {
                let newIdx = idx + 1
                parent.historyIndex = newIdx
                setTextFromHistory(parent.history[newIdx], in: textView)
            }
        }

        private func setTextFromHistory(_ value: String, in textView: NSTextView) {
            isUpdating = true
            textView.string = value
            parent.text = value
            // Move cursor to end
            textView.setSelectedRange(NSRange(location: value.count, length: 0))
            isUpdating = false
            updatePlaceholder()
        }
    }
}

// MARK: - Custom NSTextView Subclass

/// NSTextView subclass that intercepts key events for CLI-style behavior.
class CLIInputTextView: NSTextView {
    weak var coordinator: CLITextView.Coordinator?

    override func keyDown(with event: NSEvent) {
        if let coordinator = coordinator, coordinator.handleKeyDown(event, in: self) {
            return // Event was handled
        }
        super.keyDown(with: event)
    }
}

// MARK: - Intrinsic Height Calculation

/// Calculates the ideal height for the CLITextView based on its content.
/// Min 1 line (~30pt), max ~8 lines or 40% of parent.
struct CLITextViewHeightKey: PreferenceKey {
    nonisolated(unsafe) static var defaultValue: CGFloat = 36
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}
