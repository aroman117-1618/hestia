import SwiftUI

// MARK: - iOS Typography — Liquid Glass Design System

/// Centralized font tokens for iOS views.
/// Mirrors the macOS MacTypography enum for cross-platform consistency.
extension Font {
    /// 32pt Semibold — dashboard hero numbers, large stats
    static let glassHero: Font = .system(size: 32, weight: .semibold)
    /// 22pt Semibold — page titles
    static let glassTitle: Font = .system(size: 22, weight: .semibold)
    /// 18pt Medium — section headings
    static let glassHeading: Font = .system(size: 18, weight: .medium)
    /// 15pt Medium — card titles, list group headers
    static let glassSubheading: Font = .system(size: 15, weight: .medium)
    /// 14pt Regular — default body text
    static let glassBody: Font = .system(size: 14)
    /// 14pt Medium — emphasized body
    static let glassBodyMedium: Font = .system(size: 14, weight: .medium)
    /// 12pt Regular — timestamps, metadata
    static let glassCaption: Font = .system(size: 12)
    /// 12pt Medium — badge labels, tab labels
    static let glassCaptionMedium: Font = .system(size: 12, weight: .medium)
    /// 10pt Medium — axis labels, fine print
    static let glassMicro: Font = .system(size: 10, weight: .medium)
    /// 13pt Regular Monospaced — code blocks
    static let glassCode: Font = .system(size: 13, design: .monospaced)
    /// 11pt Semibold — section labels (use with .tracking(0.8).textCase(.uppercase))
    static let glassSectionLabel: Font = .system(size: 11, weight: .semibold)
    /// 15pt Regular — text fields, chat input
    static let glassInput: Font = .system(size: 15)
    /// 15pt Regular — chat message body
    static let glassChat: Font = .system(size: 15)
    /// 13pt Medium — message sender labels
    static let glassChatSender: Font = .system(size: 13, weight: .medium)
}
