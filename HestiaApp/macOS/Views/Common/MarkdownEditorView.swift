import SwiftUI
import AppKit

// MARK: - MarkdownEditorView (SwiftUI wrapper)

/// Reusable markdown editor with syntax highlighting, line numbers, and preview toggle.
/// Used for MIND.md, BODY.md, ANIMA.md, and future file editing (Explorer, Orders).
struct MarkdownEditorView: View {
    @Binding var text: String
    var isEditable: Bool = true
    var onSave: ((String) -> Void)?
    @State private var showPreview: Bool = false
    @State private var hasUnsavedChanges: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            editorToolbar

            // Content area
            if showPreview {
                markdownPreview
            } else {
                MarkdownTextEditor(
                    text: $text,
                    isEditable: isEditable,
                    onTextChange: {
                        hasUnsavedChanges = true
                    }
                )
            }
        }
        .background(MacColors.editorBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        )
    }

    // MARK: - Toolbar

    private var editorToolbar: some View {
        HStack(spacing: MacSpacing.sm) {
            // Mode toggle
            Button {
                showPreview.toggle()
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: showPreview ? "pencil" : "eye")
                        .font(.system(size: 11))
                    Text(showPreview ? "Edit" : "Preview")
                        .font(MacTypography.caption)
                }
                .foregroundStyle(MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 4)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
            .accessibilityLabel(showPreview ? "Switch to edit mode" : "Switch to preview mode")

            Spacer()

            // Unsaved indicator
            if hasUnsavedChanges {
                Circle()
                    .fill(MacColors.amberAccent)
                    .frame(width: 6, height: 6)
                    .accessibilityLabel("Unsaved changes")
            }

            // Character count
            Text("\(text.count) chars")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.editorBackgroundAlt)
    }

    // MARK: - Preview

    private var markdownPreview: some View {
        ScrollView {
            Text(text)
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(MacSpacing.lg)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - NSTextView Wrapper

struct MarkdownTextEditor: NSViewRepresentable {
    @Binding var text: String
    var isEditable: Bool
    var showLineNumbers: Bool = true
    var onTextChange: (() -> Void)?

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false

        let textView = MarkdownNSTextView()
        textView.delegate = context.coordinator
        textView.isEditable = isEditable
        textView.isSelectable = true
        textView.isRichText = false
        textView.allowsUndo = true
        textView.usesFindPanel = true
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.isAutomaticTextReplacementEnabled = false
        textView.isAutomaticSpellingCorrectionEnabled = false

        // Appearance
        textView.backgroundColor = NSColor(red: 0.118, green: 0.118, blue: 0.118, alpha: 1.0) // #1E1E1E
        textView.insertionPointColor = NSColor(red: 0.878, green: 0.627, blue: 0.314, alpha: 1.0) // amber
        textView.font = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
        textView.textColor = NSColor(red: 0.894, green: 0.875, blue: 0.843, alpha: 1.0) // textPrimary

        // Layout
        textView.textContainerInset = NSSize(width: 12, height: 12)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(
            width: scrollView.contentSize.width,
            height: CGFloat.greatestFiniteMagnitude
        )

        scrollView.documentView = textView
        context.coordinator.textView = textView

        // Line numbers via vertical ruler
        if showLineNumbers {
            let rulerView = LineNumberRulerView(textView: textView)
            scrollView.hasVerticalRuler = true
            scrollView.verticalRulerView = rulerView
            scrollView.rulersVisible = true
            context.coordinator.rulerView = rulerView
        }

        // Set initial text and apply highlighting
        textView.string = text
        context.coordinator.applyMarkdownHighlighting(textView)

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? MarkdownNSTextView else { return }
        if textView.string != text {
            let selectedRanges = textView.selectedRanges
            textView.string = text
            context.coordinator.applyMarkdownHighlighting(textView)
            textView.selectedRanges = selectedRanges
        }
        textView.isEditable = isEditable
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: MarkdownTextEditor
        weak var textView: MarkdownNSTextView?
        weak var rulerView: LineNumberRulerView?

        // Syntax highlighting colors
        private let headerColor = NSColor(red: 0.878, green: 0.627, blue: 0.314, alpha: 1.0) // amber
        private let boldColor = NSColor(red: 0.922, green: 0.878, blue: 0.820, alpha: 1.0) // brighter
        private let codeColor = NSColor(red: 0.6, green: 0.8, blue: 0.6, alpha: 1.0) // green tint
        private let linkColor = NSColor(red: 0.4, green: 0.7, blue: 1.0, alpha: 1.0) // blue
        private let listColor = NSColor(red: 0.878, green: 0.627, blue: 0.314, alpha: 0.7) // dimmed amber
        private let defaultColor = NSColor(red: 0.894, green: 0.875, blue: 0.843, alpha: 1.0) // textPrimary

        init(_ parent: MarkdownTextEditor) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
            parent.onTextChange?()
            applyMarkdownHighlighting(textView)
            rulerView?.needsDisplay = true
        }

        func applyMarkdownHighlighting(_ textView: NSTextView) {
            let text = textView.string
            let fullRange = NSRange(location: 0, length: (text as NSString).length)
            let storage = textView.textStorage!
            let monoFont = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
            let boldFont = NSFont.monospacedSystemFont(ofSize: 13, weight: .bold)

            storage.beginEditing()

            // Reset to defaults
            storage.addAttributes([
                .foregroundColor: defaultColor,
                .font: monoFont
            ], range: fullRange)

            let nsText = text as NSString

            // Headers: lines starting with # (up to 6 levels)
            applyPattern(#"^#{1,6}\s+.*$"#, to: storage, in: nsText, color: headerColor, font: boldFont)

            // Bold: **text**
            applyPattern(#"\*\*[^*]+\*\*"#, to: storage, in: nsText, color: boldColor, font: boldFont)

            // Inline code: `text`
            applyPattern(#"`[^`]+`"#, to: storage, in: nsText, color: codeColor, font: monoFont)

            // Code blocks: ```...```
            applyPattern(#"```[\s\S]*?```"#, to: storage, in: nsText, color: codeColor, font: monoFont)

            // Links: [text](url)
            applyPattern(#"\[([^\]]+)\]\([^)]+\)"#, to: storage, in: nsText, color: linkColor, font: monoFont)

            // List markers: - or * or numbered
            applyPattern(#"^[\s]*[-*]\s"#, to: storage, in: nsText, color: listColor, font: monoFont)
            applyPattern(#"^[\s]*\d+\.\s"#, to: storage, in: nsText, color: listColor, font: monoFont)

            storage.endEditing()
        }

        private func applyPattern(
            _ pattern: String,
            to storage: NSTextStorage,
            in text: NSString,
            color: NSColor,
            font: NSFont
        ) {
            guard let regex = try? NSRegularExpression(
                pattern: pattern,
                options: [.anchorsMatchLines]
            ) else { return }

            let fullRange = NSRange(location: 0, length: text.length)
            regex.enumerateMatches(in: text as String, range: fullRange) { match, _, _ in
                guard let matchRange = match?.range else { return }
                storage.addAttributes([
                    .foregroundColor: color,
                    .font: font
                ], range: matchRange)
            }
        }
    }
}

// MARK: - Custom NSTextView subclass

class MarkdownNSTextView: NSTextView {
    override func didChangeText() {
        super.didChangeText()
        // Notify the ruler to redraw when text changes
        enclosingScrollView?.verticalRulerView?.needsDisplay = true
    }
}

// MARK: - Line Number Ruler

class LineNumberRulerView: NSRulerView {
    private weak var textView: NSTextView?
    private let gutterWidth: CGFloat = 40
    private let lineNumberFont = NSFont.monospacedDigitSystemFont(ofSize: 10, weight: .regular)
    private let lineNumberColor = NSColor(red: 0.922, green: 0.875, blue: 0.820, alpha: 0.3) // MacColors.textFaint equivalent

    init(textView: NSTextView) {
        self.textView = textView
        super.init(scrollView: textView.enclosingScrollView!, orientation: .verticalRuler)
        self.ruleThickness = gutterWidth
        self.clientView = textView

        // Observe text and layout changes
        NotificationCenter.default.addObserver(
            self, selector: #selector(textDidChange),
            name: NSText.didChangeNotification, object: textView
        )
        NotificationCenter.default.addObserver(
            self, selector: #selector(boundsDidChange),
            name: NSView.boundsDidChangeNotification, object: scrollView?.contentView
        )
    }

    @available(*, unavailable)
    required init(coder: NSCoder) {
        fatalError("init(coder:) not supported")
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    @objc private func textDidChange(_ notification: Notification) {
        needsDisplay = true
    }

    @objc private func boundsDidChange(_ notification: Notification) {
        needsDisplay = true
    }

    override func drawHashMarksAndLabels(in rect: NSRect) {
        guard let textView = textView,
              let layoutManager = textView.layoutManager,
              let textContainer = textView.textContainer else { return }

        // Fill gutter background
        let bgColor = NSColor(red: 0.09, green: 0.09, blue: 0.09, alpha: 1.0) // slightly darker than editor
        bgColor.setFill()
        rect.fill()

        // Draw separator line
        let separatorColor = NSColor(red: 0.922, green: 0.875, blue: 0.820, alpha: 0.08)
        separatorColor.setStroke()
        let separatorPath = NSBezierPath()
        separatorPath.move(to: NSPoint(x: gutterWidth - 0.5, y: rect.minY))
        separatorPath.line(to: NSPoint(x: gutterWidth - 0.5, y: rect.maxY))
        separatorPath.lineWidth = 1
        separatorPath.stroke()

        let text = textView.string as NSString
        let visibleRect = scrollView?.contentView.bounds ?? .zero
        let textInset = textView.textContainerInset

        let attrs: [NSAttributedString.Key: Any] = [
            .font: lineNumberFont,
            .foregroundColor: lineNumberColor
        ]

        // Walk visible lines
        let glyphRange = layoutManager.glyphRange(forBoundingRect: visibleRect, in: textContainer)
        var lineNumber = 1

        // Count newlines before the visible range to get the starting line number
        let charIndex = layoutManager.characterIndexForGlyph(at: glyphRange.location)
        if charIndex > 0 {
            let precedingText = text.substring(to: charIndex)
            lineNumber = precedingText.components(separatedBy: "\n").count
        }

        var glyphIndex = glyphRange.location
        while glyphIndex < NSMaxRange(glyphRange) {
            let charRange = layoutManager.characterRange(forGlyphRange: NSRange(location: glyphIndex, length: 1), actualGlyphRange: nil)
            var lineRect = NSRect.zero
            layoutManager.lineFragmentRect(forGlyphAt: glyphIndex, effectiveRange: nil, withoutAdditionalLayout: true)
            lineRect = layoutManager.lineFragmentRect(forGlyphAt: glyphIndex, effectiveRange: nil)

            // Convert to ruler coordinate space
            let yPosition = lineRect.minY + textInset.height - visibleRect.origin.y

            // Only draw if the line fragment starts at a line boundary
            let lineStart = text.lineRange(for: NSRange(location: charRange.location, length: 0)).location
            if charRange.location == lineStart {
                let lineStr = "\(lineNumber)" as NSString
                let strSize = lineStr.size(withAttributes: attrs)
                let drawPoint = NSPoint(
                    x: gutterWidth - strSize.width - 8,
                    y: yPosition + (lineRect.height - strSize.height) / 2
                )
                lineStr.draw(at: drawPoint, withAttributes: attrs)
                lineNumber += 1
            }

            // Advance past this line fragment
            var nextGlyphRange = NSRange()
            layoutManager.lineFragmentRect(forGlyphAt: glyphIndex, effectiveRange: &nextGlyphRange)
            glyphIndex = NSMaxRange(nextGlyphRange)
        }
    }
}
