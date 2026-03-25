import SwiftUI

// MARK: - macOS Typography — Liquid Glass Design System

enum MacTypography {
    // MARK: - Brand
    static let brand = Font.custom("Volkhov-Bold", size: 28)

    // MARK: - Headings
    static let heroNumber = Font.system(size: 32, weight: .semibold)
    static let largeValue = Font.system(size: 32)
    static let mediumValue = Font.system(size: 22)
    static let pageTitle = Font.system(size: 18)

    // MARK: - Section Headers
    static let sectionTitle = Font.system(size: 15, weight: .medium)
    static let cardTitle = Font.system(size: 15, weight: .medium)
    static let sectionLabel = Font.system(size: 11, weight: .semibold)
    // Usage: .font(MacTypography.sectionLabel).tracking(0.8).textCase(.uppercase)

    // MARK: - Body
    static let chatMessage = Font.system(size: 15)
    static let body = Font.system(size: 14)
    static let bodyMedium = Font.system(size: 14, weight: .medium)
    static let inputField = Font.system(size: 15)

    // MARK: - Labels & Metadata
    static let label = Font.system(size: 12)
    static let labelMedium = Font.system(size: 12, weight: .medium)
    static let smallBody = Font.system(size: 12)
    static let smallMedium = Font.system(size: 12, weight: .medium)
    static let senderLabel = Font.system(size: 13, weight: .medium)

    // MARK: - Small / Captions
    static let caption = Font.system(size: 12)
    static let captionMedium = Font.system(size: 12, weight: .medium)
    static let metadata = Font.system(size: 10)
    static let micro = Font.system(size: 10, weight: .medium)
    static let axis = Font.system(size: 10, weight: .medium)

    // MARK: - Monospace
    static let code = Font.system(size: 13, design: .monospaced)

    // MARK: - Aliases (non-spec tokens mapped to spec equivalents)
    static let heroHeading = brand
    static let cardSubtitle = senderLabel
}

// MARK: - View Modifiers

extension View {
    func macSectionHeader() -> some View {
        self
            .font(MacTypography.labelMedium)
            .foregroundStyle(MacColors.textSecondary)
    }
}
