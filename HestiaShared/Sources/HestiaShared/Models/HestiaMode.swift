import SwiftUI

/// The three personas/modes of Hestia
public enum HestiaMode: String, Codable, CaseIterable, Identifiable, Sendable {
    case tia
    case mira
    case olly

    public var id: String { rawValue }

    /// Short display name
    public var displayName: String {
        switch self {
        case .tia: return "Tia"
        case .mira: return "Mira"
        case .olly: return "Olly"
        }
    }

    /// Full persona name
    public var fullName: String {
        switch self {
        case .tia: return "Hestia"
        case .mira: return "Artemis"
        case .olly: return "Apollo"
        }
    }

    /// Description of the mode's purpose
    public var description: String {
        switch self {
        case .tia: return "Daily operations & quick queries"
        case .mira: return "Learning & Socratic teaching"
        case .olly: return "Focused project work"
        }
    }

    /// Mode-specific gradient colors (from Figma)
    public var gradientColors: [Color] {
        switch self {
        case .tia: return Color.tiaGradientColors
        case .mira: return Color.miraGradientColors
        case .olly: return Color.ollyGradientColors
        }
    }

    /// Pre-built linear gradient
    public var gradient: LinearGradient {
        LinearGradient(
            colors: gradientColors,
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    /// Invocation pattern (what users type to switch)
    public var invokePattern: String {
        switch self {
        case .tia: return "@tia"
        case .mira: return "@mira"
        case .olly: return "@olly"
        }
    }

    /// Personality traits for display
    public var traits: [String] {
        switch self {
        case .tia:
            return [
                "Efficient and direct",
                "Competent without being showy",
                "Occasionally sardonic wit"
            ]
        case .mira:
            return [
                "Socratic teaching style",
                "Asks clarifying questions",
                "Encourages exploration"
            ]
        case .olly:
            return [
                "Focused and task-oriented",
                "Minimal tangents",
                "Project completion mindset"
            ]
        }
    }

    /// Asset catalog image name for the avatar (nil if no custom image)
    public var avatarImageName: String? {
        switch self {
        case .tia: return "hestia-profile"
        case .mira: return "artemis-profile"
        case .olly: return "apollo-profile"
        }
    }

    /// Returns the avatar Image if available, otherwise nil
    public var avatarImage: Image? {
        guard let imageName = avatarImageName else { return nil }
        return Image(imageName)
    }
}

// MARK: - Persona Info (API Response)

/// Detailed persona information from the backend
public struct PersonaInfo: Codable, Sendable {
    public let mode: String
    public let name: String
    public let fullName: String
    public let description: String
    public let traits: [String]

    public init(mode: String, name: String, fullName: String, description: String, traits: [String]) {
        self.mode = mode
        self.name = name
        self.fullName = fullName
        self.description = description
        self.traits = traits
    }

    enum CodingKeys: String, CodingKey {
        case mode
        case name
        case fullName = "full_name"
        case description
        case traits
    }
}
