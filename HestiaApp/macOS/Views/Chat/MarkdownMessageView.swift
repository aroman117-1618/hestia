import SwiftUI
import AppKit

// MARK: - Markdown Message View

/// Renders AI message content with rich markdown support:
/// - Inline formatting (bold, italic, code, links) via AttributedString
/// - Fenced code blocks with syntax label and copy button
/// - Tool call cards with collapsible detail
struct MarkdownMessageView: View {
    let content: String

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            ForEach(Array(segments.enumerated()), id: \.offset) { _, segment in
                segmentView(for: segment)
            }
        }
    }

    // MARK: - Segment Parsing

    private var segments: [ContentSegment] {
        parseContent(content)
    }

    @ViewBuilder
    private func segmentView(for segment: ContentSegment) -> some View {
        switch segment {
        case .text(let str):
            inlineMarkdownText(str)
        case .codeBlock(let language, let code):
            CodeBlockView(language: language, code: code)
        case .toolCall(let name, let result):
            ToolCallCardView(toolName: name, result: result)
        }
    }

    // MARK: - Inline Markdown Rendering

    @ViewBuilder
    private func inlineMarkdownText(_ text: String) -> some View {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            if let attributed = try? AttributedString(markdown: trimmed, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
                Text(attributed)
                    .font(MacTypography.chatMessage)
                    .foregroundStyle(MacColors.textPrimary)
                    .tint(MacColors.amberAccent)
                    .textSelection(.enabled)
            } else {
                Text(trimmed)
                    .font(MacTypography.chatMessage)
                    .foregroundStyle(MacColors.textPrimary)
                    .textSelection(.enabled)
            }
        }
    }
}

// MARK: - Content Segment

private enum ContentSegment {
    case text(String)
    case codeBlock(language: String?, code: String)
    case toolCall(name: String, result: String)
}

// MARK: - Content Parser

/// Parses message content into segments: plain text, fenced code blocks, and tool calls.
private func parseContent(_ content: String) -> [ContentSegment] {
    var segments: [ContentSegment] = []
    let lines = content.components(separatedBy: "\n")
    var currentText = ""
    var inCodeBlock = false
    var codeBlockLanguage: String?
    var codeBlockContent = ""

    for line in lines {
        if !inCodeBlock {
            // Check for code block start
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                // Flush accumulated text
                if !currentText.isEmpty {
                    // Check for tool call markers in accumulated text
                    let toolSegments = extractToolCalls(from: currentText)
                    segments.append(contentsOf: toolSegments)
                    currentText = ""
                }

                inCodeBlock = true
                let langLine = line.trimmingCharacters(in: .whitespaces)
                    .dropFirst(3)
                    .trimmingCharacters(in: .whitespaces)
                codeBlockLanguage = langLine.isEmpty ? nil : langLine
                codeBlockContent = ""
            } else {
                if !currentText.isEmpty {
                    currentText += "\n"
                }
                currentText += line
            }
        } else {
            // Inside code block
            if line.trimmingCharacters(in: .whitespaces) == "```" {
                // End code block
                inCodeBlock = false
                segments.append(.codeBlock(language: codeBlockLanguage, code: codeBlockContent))
                codeBlockLanguage = nil
                codeBlockContent = ""
            } else {
                if !codeBlockContent.isEmpty {
                    codeBlockContent += "\n"
                }
                codeBlockContent += line
            }
        }
    }

    // Flush remaining content
    if inCodeBlock {
        // Unclosed code block — treat as code anyway
        segments.append(.codeBlock(language: codeBlockLanguage, code: codeBlockContent))
    } else if !currentText.isEmpty {
        let toolSegments = extractToolCalls(from: currentText)
        segments.append(contentsOf: toolSegments)
    }

    return segments
}

/// Extracts tool call markers from text, splitting into text and toolCall segments.
private func extractToolCalls(from text: String) -> [ContentSegment] {
    // Look for patterns like [tool:tool_name] result... or {"tool_call": ...}
    // Simple heuristic: detect JSON-like tool call blocks
    let toolCallPattern = #"\[tool:([^\]]+)\]\s*(.*?)(?=\[tool:|$)"#

    guard let regex = try? NSRegularExpression(pattern: toolCallPattern, options: [.dotMatchesLineSeparators]) else {
        return [.text(text)]
    }

    let nsText = text as NSString
    let matches = regex.matches(in: text, range: NSRange(location: 0, length: nsText.length))

    if matches.isEmpty {
        // Also check for JSON tool_call markers
        if text.contains("\"tool_call\"") || text.contains("{\"tool_call\"") {
            return [.toolCall(name: "Tool Execution", result: text)]
        }
        return [.text(text)]
    }

    var segments: [ContentSegment] = []
    var lastEnd = 0

    for match in matches {
        // Text before tool call
        if match.range.location > lastEnd {
            let preRange = NSRange(location: lastEnd, length: match.range.location - lastEnd)
            let preText = nsText.substring(with: preRange)
            if !preText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                segments.append(.text(preText))
            }
        }

        let toolName = nsText.substring(with: match.range(at: 1))
        let toolResult = nsText.substring(with: match.range(at: 2))
        segments.append(.toolCall(name: toolName, result: toolResult.trimmingCharacters(in: .whitespacesAndNewlines)))

        lastEnd = match.range.location + match.range.length
    }

    // Remaining text
    if lastEnd < nsText.length {
        let remaining = nsText.substring(from: lastEnd)
        if !remaining.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            segments.append(.text(remaining))
        }
    }

    return segments
}

// MARK: - Code Block View

/// Renders a fenced code block with dark panel, language label, and copy button.
struct CodeBlockView: View {
    let language: String?
    let code: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header bar with language label and copy button
            HStack {
                if let lang = language, !lang.isEmpty {
                    Text(lang)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }
                Spacer()
                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(code, forType: .string)
                    copied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        copied = false
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 10))
                        Text(copied ? "Copied" : "Copy")
                            .font(MacTypography.caption)
                    }
                    .foregroundStyle(copied ? MacColors.healthGreen : MacColors.textSecondary)
                }
                .buttonStyle(.hestiaIcon)
                .accessibilityLabel(copied ? "Code copied" : "Copy code to clipboard")
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.xs)
            .background(Color(red: 0x14 / 255, green: 0x14 / 255, blue: 0x24 / 255))

            // Code content
            ScrollView(.horizontal, showsIndicators: true) {
                Text(code)
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(Color(red: 0xE0 / 255, green: 0xE0 / 255, blue: 0xE0 / 255))
                    .textSelection(.enabled)
                    .padding(MacSpacing.md)
            }
        }
        .background(Color(red: 0x1A / 255, green: 0x1A / 255, blue: 0x2E / 255))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
        }
    }
}

// MARK: - Tool Call Card View

/// Renders a tool execution result as a card with icon, name, and collapsible detail.
struct ToolCallCardView: View {
    let toolName: String
    let result: String
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header
            Button {
                withAnimation(MacAnimation.fastSpring) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "wrench.and.screwdriver")
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.amberAccent)

                    Text(toolName)
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.textPrimary)

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(MacColors.textSecondary)
                }
            }
            .buttonStyle(.hestia)

            // Summary (always visible)
            if !isExpanded {
                Text(resultSummary)
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(2)
            }

            // Expanded detail
            if isExpanded {
                Text(result)
                    .font(MacTypography.code)
                    .foregroundStyle(MacColors.textPrimary)
                    .textSelection(.enabled)
                    .padding(MacSpacing.sm)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(MacColors.panelBackground.opacity(0.5))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay {
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(MacColors.amberAccent.opacity(0.25), lineWidth: 1)
        }
    }

    private var resultSummary: String {
        let trimmed = result.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.count <= 120 {
            return trimmed
        }
        return String(trimmed.prefix(117)) + "..."
    }
}
